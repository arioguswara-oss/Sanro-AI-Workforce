import test from 'node:test';
import assert from 'node:assert/strict';
import {createCodexAppsDriveTransport} from '../src/codex-apps-drive-adapter.js';

test('codex_apps Drive adapter scopes upload, private folder, dedupe lookup and raw readback',async()=>{
  const calls=[],bytes=Buffer.from('synthetic bytes'),folder='private-folder-123456',account='synthetic-account',fileId='synthetic-file-123456';let listing=[];
  const transport=createCodexAppsDriveTransport({
    async listFolder(args){calls.push(['list',args]);return listing;},
    async uploadFile(args){calls.push(['upload',args]);listing=[{id:fileId,name:'demo.zip',parents:[folder],permissions:[]}];return {id:fileId};},
    async getFileMetadata(args){calls.push(['metadata',args]);if(args.fileId===folder)return {id:folder,mimeType:'application/vnd.google-apps.folder',permissions:[]};return {id:fileId,name:'demo.zip',parents:[folder],permissions:[],webViewLink:`https://drive.google.com/file/d/${fileId}/view`};},
    async fetchFile(args){calls.push(['fetch',args]);return {bytes};},
  });
  assert.equal(await transport.findExisting({accountId:account,folderId:folder,filename:'demo.zip'}),null);
  assert.deepEqual(await transport.upload({accountId:account,folderId:folder,filename:'demo.zip',filePath:'/synthetic/project/demo.zip',mimeType:'application/zip',visibility:'private'}),{file_id:fileId});
  assert.deepEqual(await transport.findExisting({accountId:account,folderId:folder,filename:'demo.zip'}),{file_id:fileId});
  const read=await transport.readback({accountId:account,folderId:folder,fileId});assert.deepEqual(read.bytes,bytes);assert.equal(read.visibility,'private');
  const upload=calls.find(x=>x[0]==='upload')[1];assert.equal(upload.parent_folder_id,folder);assert.equal(upload.link_id,account);assert.equal(upload.file_uri,'/synthetic/project/demo.zip');
  assert.ok(calls.some(([name,args])=>name==='fetch'&&args.download_raw_file===true&&args.include_base64===true));
});

test('codex_apps Drive adapter rejects public folders and artifacts outside mapped folder',async()=>{
  const folder='private-folder-123456',fileId='synthetic-file-123456';let publicFolder=true,wrongParent=false;
  const transport=createCodexAppsDriveTransport({
    async listFolder(){return [{id:fileId,name:'demo.zip',parents:[wrongParent?'attacker-folder':folder],permissions:[]}];},
    async uploadFile(){throw new Error('must fail closed');},
    async getFileMetadata({fileId:id}){return id===folder?{id,mimeType:'application/vnd.google-apps.folder',permissions:publicFolder?[{type:'anyone'}]:[]}:{id,name:'demo.zip',parents:[wrongParent?'attacker-folder':folder],permissions:[]};},
    async fetchFile(){return {bytes:Buffer.from('synthetic')};},
  });
  await assert.rejects(transport.findExisting({accountId:'synthetic-account',folderId:folder,filename:'demo.zip'}),/private/);
  publicFolder=false;wrongParent=true;
  await assert.rejects(transport.findExisting({accountId:'synthetic-account',folderId:folder,filename:'demo.zip'}),/authorized private folder/);
});
