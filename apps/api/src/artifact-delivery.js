import {createHash,randomUUID} from 'node:crypto';
import {isAbsolute,basename} from 'node:path';

const shaRe=/^[a-f0-9]{64}$/;
const sourceShaRe=/^[a-f0-9]{40}(?:[a-f0-9]{24})?$/;
const states=new Set(['DEVELOPMENT','TESTING','RELEASE_CANDIDATE','APPROVED_RELEASE']);
const qaStates=new Set(['PASS','FAIL','NOT_TESTED']);
const iso=()=>new Date().toISOString();
const digest=bytes=>createHash('sha256').update(bytes).digest('hex');
function validZip(bytes){
  const min=Math.max(0,bytes.length-65557);let end=-1;
  for(let i=bytes.length-22;i>=min;i--)if(bytes.readUInt32LE(i)===0x06054b50){end=i;break;}
  if(end<0||bytes.readUInt16LE(end+4)!==0||bytes.readUInt16LE(end+6)!==0||bytes.readUInt16LE(end+8)!==bytes.readUInt16LE(end+10))return false;
  const count=bytes.readUInt16LE(end+10),size=bytes.readUInt32LE(end+12),offset=bytes.readUInt32LE(end+16);
  if(count===0)return size===0&&offset===end;
  if(count===0xffff||size===0xffffffff||offset===0xffffffff||offset+size>end)return false;
  let cursor=offset;
  for(let n=0;n<count;n++){
    if(cursor+46>bytes.length||bytes.readUInt32LE(cursor)!==0x02014b50)return false;
    const name=bytes.readUInt16LE(cursor+28),extra=bytes.readUInt16LE(cursor+30),comment=bytes.readUInt16LE(cursor+32),local=bytes.readUInt32LE(cursor+42);
    if(local+30>bytes.length||bytes.readUInt32LE(local)!==0x04034b50)return false;
    cursor+=46+name+extra+comment;
  }
  return cursor===offset+size&&cursor===end;
}

export function ensureArtifactTables(db){
  db.exec(`CREATE TABLE IF NOT EXISTS artifact_deliveries(
    delivery_key TEXT PRIMARY KEY, project_id TEXT NOT NULL, artifact_sha256 TEXT NOT NULL,
    folder_id TEXT NOT NULL, account_id TEXT NOT NULL, status TEXT NOT NULL,
    manifest_json TEXT NOT NULL, checkpoint_json TEXT NOT NULL, remote_file_id TEXT,
    download_link TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    UNIQUE(project_id,artifact_sha256,folder_id));`);
  const columns=new Set(db.prepare('PRAGMA table_info(report_outbox)').all().map(x=>x.name));
  if(!columns.has('delivery_status'))db.exec("ALTER TABLE report_outbox ADD COLUMN delivery_status TEXT NOT NULL DEFAULT 'QUEUED'");
  if(!columns.has('delivered_at'))db.exec('ALTER TABLE report_outbox ADD COLUMN delivered_at TEXT');
}

export function validateArtifactManifest(manifest,bytes){
  const required=['schema_version','project_id','artifact_filename','version','release_status','source_commit_sha','build_timestamp','file_size','sha256','release_notes','qa_status','owner_release_approval'];
  if(!manifest||typeof manifest!=='object'||Array.isArray(manifest)||Object.keys(manifest).sort().join('|')!==required.sort().join('|'))throw new Error('artifact manifest fields are incomplete or unexpected');
  if(manifest.schema_version!==1||typeof manifest.project_id!=='string'||!/^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/.test(manifest.project_id))throw new Error('artifact project metadata is invalid');
  if(typeof manifest.artifact_filename!=='string'||basename(manifest.artifact_filename)!==manifest.artifact_filename||!(/\.zip$/i.test(manifest.artifact_filename)||/\.apk$/i.test(manifest.artifact_filename)))throw new Error('artifact filename must be a ZIP/APK basename');
  if(typeof manifest.version!=='string'||!/^[A-Za-z0-9][A-Za-z0-9.+_-]{0,63}$/.test(manifest.version)||!states.has(manifest.release_status)||!qaStates.has(manifest.qa_status))throw new Error('artifact version or release metadata is invalid');
  if(!sourceShaRe.test(manifest.source_commit_sha)||!Number.isFinite(Date.parse(manifest.build_timestamp))||!Number.isSafeInteger(manifest.file_size)||manifest.file_size<=0||typeof manifest.release_notes!=='string'||!manifest.release_notes.trim()||manifest.release_notes.length>4000)throw new Error('artifact provenance metadata is incomplete');
  if((manifest.release_status==='RELEASE_CANDIDATE'||manifest.release_status==='APPROVED_RELEASE')&&manifest.qa_status!=='PASS')throw new Error('release artifact requires passing QA');
  if(manifest.release_status==='APPROVED_RELEASE'&&(typeof manifest.owner_release_approval!=='string'||manifest.owner_release_approval.length<8))throw new Error('approved release requires a distinct Owner approval reference');
  if(manifest.release_status!=='APPROVED_RELEASE'&&manifest.owner_release_approval!==null)throw new Error('release approval metadata conflicts with development status');
  if(!Buffer.isBuffer(bytes)||bytes.length!==manifest.file_size||!validZip(bytes)||!shaRe.test(manifest.sha256)||digest(bytes)!==manifest.sha256)throw new Error('artifact bytes do not match the manifest');
  return manifest;
}

const privateFolder=(mapping,projectId)=>{
  if(!mapping||mapping.project_id!==projectId||typeof mapping.folder_id!=='string'||!mapping.folder_id||typeof mapping.account_id!=='string'||!mapping.account_id||mapping.visibility!=='private')throw new Error('authorized private Drive folder mapping required');
  return mapping;
};

export function queueArtifactReport(db,{manifest,delivery}){
  if(delivery.status!=='VERIFIED'||!delivery.download_link||!delivery.remote_file_id)throw new Error('only remotely read-back-verified artifacts can enter reports');
  const key=`artifact:${manifest.project_id}:${manifest.sha256}`;
  const payload={version:1,event:'ARTIFACT_VERIFIED',project_id:manifest.project_id,delivery_key:key,artifact:{filename:manifest.artifact_filename,version:manifest.version,release_status:manifest.release_status,source_commit_sha:manifest.source_commit_sha,sha256:manifest.sha256,file_size:manifest.file_size,qa_status:manifest.qa_status,download_link:delivery.download_link,drive_status:'VERIFIED'},telegram_status:'QUEUED'};
  db.prepare('INSERT OR IGNORE INTO report_outbox(id,project_id,owner,run_id,delivery_key,payload,created_at,delivered_at,delivery_status) VALUES(?,?,?,?,?,?,?,?,?)').run(randomUUID(),manifest.project_id,'artifact-delivery',key,key,JSON.stringify(payload),iso(),null,'QUEUED');
  return {delivery_key:key,status:'QUEUED'};
}

/** Injected provider boundary. This class does no networking or sharing itself. */
export class ProjectDriveArtifactDelivery{
  constructor({db,projectId,mapping,transport}){
    ensureArtifactTables(db);Object.assign(this,{db,projectId,mapping:privateFolder(mapping,projectId),transport});
    if(typeof transport?.findExisting!=='function'||typeof transport?.upload!=='function'||typeof transport?.readback!=='function')throw new Error('Drive deduplication, upload and readback adapter methods are required');
  }
  async deliver(manifest,bytes,{filePath=null}={}){
    validateArtifactManifest(manifest,bytes);
    if(manifest.project_id!==this.projectId)throw new Error('artifact project does not match the authorized folder');
    const key=`${this.projectId}:${manifest.sha256}:${this.mapping.folder_id}`;
    let row=this.db.prepare('SELECT * FROM artifact_deliveries WHERE delivery_key=?').get(key);
    if(row?.status==='VERIFIED'){
      const delivery={status:'VERIFIED',remote_file_id:row.remote_file_id,download_link:row.download_link};
      try{queueArtifactReport(this.db,{manifest,delivery});this._checkpoint(row,'VERIFIED',{report_state:'QUEUED'});}catch{this._checkpoint(row,'VERIFIED',{report_state:'FAILED'});throw new Error('artifact verified; report checkpoint failed');}
      return {...delivery,deduplicated:true};
    }
    const now=iso(),checkpoint={state:'UPLOADING',project_id:this.projectId,artifact_sha256:manifest.sha256,folder_id:this.mapping.folder_id,account_id:this.mapping.account_id,updated_at:now};
    this.db.prepare(`INSERT INTO artifact_deliveries(delivery_key,project_id,artifact_sha256,folder_id,account_id,status,manifest_json,checkpoint_json,created_at,updated_at)
      VALUES(?,?,?,?,?,'UPLOADING',?,?,?,?) ON CONFLICT(delivery_key) DO UPDATE SET status='UPLOADING',checkpoint_json=excluded.checkpoint_json,updated_at=excluded.updated_at`).run(key,this.projectId,manifest.sha256,this.mapping.folder_id,this.mapping.account_id,JSON.stringify(manifest),JSON.stringify(checkpoint),now,now);
    row=this.db.prepare('SELECT * FROM artifact_deliveries WHERE delivery_key=?').get(key);
    try{
      const existing=await this.transport.findExisting({accountId:this.mapping.account_id,folderId:this.mapping.folder_id,filename:manifest.artifact_filename,sha256:manifest.sha256,idempotencyKey:key});
      if(Array.isArray(existing)||existing&&typeof existing.file_id!=='string')throw new Error('Drive duplicate lookup is ambiguous');
      const uploaded=existing??await this.transport.upload({accountId:this.mapping.account_id,folderId:this.mapping.folder_id,filename:manifest.artifact_filename,filePath,bytes,mimeType:/\.apk$/i.test(manifest.artifact_filename)?'application/vnd.android.package-archive':'application/zip',visibility:'private',idempotencyKey:key});
      if(!uploaded||typeof uploaded.file_id!=='string'||!uploaded.file_id)throw new Error('invalid remote file identity');
      this._checkpoint(row,'UPLOADED',{remote_file_id:uploaded.file_id,upload_status:'UPLOADED'});
      const remote=await this.transport.readback({accountId:this.mapping.account_id,folderId:this.mapping.folder_id,fileId:uploaded.file_id});
      if(!remote||remote.file_id!==uploaded.file_id||remote.account_id!==this.mapping.account_id||remote.folder_id!==this.mapping.folder_id||remote.visibility!=='private'||!Buffer.isBuffer(remote.bytes)||digest(remote.bytes)!==manifest.sha256||remote.bytes.length!==manifest.file_size)throw new Error('remote artifact integrity or folder validation failed');
      if(typeof remote.download_link!=='string'||!/^https:\/\/drive\.google\.com\/file\/d\/[A-Za-z0-9_-]+\/view$/.test(remote.download_link))throw new Error('private Drive readback link is invalid');
      const delivery={status:'VERIFIED',remote_file_id:uploaded.file_id,download_link:remote.download_link};
      const verified={...JSON.parse(row.checkpoint_json),state:'VERIFIED',remote_file_id:uploaded.file_id,download_link:remote.download_link,remote_sha256:digest(remote.bytes),verified_at:iso()};
      this.db.prepare("UPDATE artifact_deliveries SET status='VERIFIED',remote_file_id=?,download_link=?,checkpoint_json=?,updated_at=? WHERE delivery_key=?").run(uploaded.file_id,remote.download_link,JSON.stringify(verified),iso(),key);
      try{queueArtifactReport(this.db,{manifest,delivery});}catch{verified.report_state='FAILED';this.db.prepare('UPDATE artifact_deliveries SET checkpoint_json=? WHERE delivery_key=?').run(JSON.stringify(verified),key);throw new Error('artifact verified; report checkpoint failed');}
      verified.report_state='QUEUED';this.db.prepare('UPDATE artifact_deliveries SET checkpoint_json=? WHERE delivery_key=?').run(JSON.stringify(verified),key);
      return delivery;
    }catch(error){
      const state=this.db.prepare('SELECT * FROM artifact_deliveries WHERE delivery_key=?').get(key),failed={...JSON.parse(state.checkpoint_json),state:state.status==='VERIFIED'?'VERIFIED':'FAILED',failure_code:/interrupted|timeout/i.test(String(error?.message))?'UPLOAD_INTERRUPTED':'DELIVERY_OR_INTEGRITY_FAILURE',report_state:state.status==='VERIFIED'?'FAILED':undefined,failed_at:iso()};
      if(failed.report_state===undefined)delete failed.report_state;
      this.db.prepare('UPDATE artifact_deliveries SET status=?,checkpoint_json=?,updated_at=? WHERE delivery_key=?').run(failed.state,JSON.stringify(failed),iso(),key);
      throw error;
    }
  }
  _checkpoint(row,status,extra){
    const checkpoint={...JSON.parse(row.checkpoint_json),...extra,state:status,updated_at:iso()};
    this.db.prepare('UPDATE artifact_deliveries SET status=?,checkpoint_json=?,updated_at=? WHERE delivery_key=?').run(status,JSON.stringify(checkpoint),iso(),row.delivery_key);
  }
}
