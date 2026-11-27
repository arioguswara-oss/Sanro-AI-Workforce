/**
 * Normalize the existing codex_apps Google Drive MCP operations for the
 * project-scoped artifact delivery contract. Callbacks are injected by the
 * host; this module performs no network calls and has no credentials.
 */
export function createCodexAppsDriveTransport({listFolder,uploadFile,getFileMetadata,fetchFile}){
  for(const [name,fn] of Object.entries({listFolder,uploadFile,getFileMetadata,fetchFile}))if(typeof fn!=='function')throw new Error(`Google Drive MCP callback ${name} is required`);
  const assertPrivateFolder=async(accountId,folderId)=>{
    const folder=await getFileMetadata({fileId:folderId,link_id:accountId,fields:'id,mimeType,permissions,shared'});
    if(folder?.id!==folderId||folder.mimeType!=='application/vnd.google-apps.folder'||(folder.permissions??[]).some(p=>p?.type==='anyone'))throw new Error('Drive folder is not authorized and private');
  };
  const privateFile=(file,folderId)=>file&&typeof file.id==='string'&&Array.isArray(file.parents)&&file.parents.includes(folderId)&&!(file.permissions??[]).some(p=>p?.type==='anyone');
  return {
    async findExisting({accountId,folderId,filename}){
      await assertPrivateFolder(accountId,folderId);
      const items=await listFolder({link_id:accountId,url:`https://drive.google.com/drive/folders/${folderId}`,top_k:100});
      if(!Array.isArray(items))throw new Error('Drive folder listing must be normalized to file metadata');
      const matches=items.filter(file=>file?.name===filename);
      if(matches.length>1)throw new Error('multiple matching Drive artifacts require manual reconciliation');
      if(!matches.length)return null;
      if(!privateFile(matches[0],folderId))throw new Error('existing Drive artifact is outside the authorized private folder');
      return {file_id:matches[0].id};
    },
    async upload({accountId,folderId,filename,filePath,mimeType,visibility}){
      await assertPrivateFolder(accountId,folderId);
      if(visibility!=='private'||typeof filePath!=='string'||!filePath.startsWith('/'))throw new Error('private project artifact file is required');
      const result=await uploadFile({file_uri:filePath,file_name:filename,mime_type:mimeType,parent_folder_id:folderId,link_id:accountId});
      const id=result?.file_id??result?.id;
      if(typeof id!=='string'||!id)throw new Error('Google Drive upload returned no file ID');
      return {file_id:id};
    },
    async readback({accountId,folderId,fileId}){
      await assertPrivateFolder(accountId,folderId);
      const file=await getFileMetadata({fileId,link_id:accountId,fields:'id,name,mimeType,parents,webViewLink,permissions,shared,size'});
      if(!privateFile(file,folderId))throw new Error('Drive readback file or folder ACL is not authorized');
      if(!/^[A-Za-z0-9_-]{8,200}$/.test(file.id))throw new Error('Drive file ID is invalid');
      const result=await fetchFile({url:`https://drive.google.com/file/d/${file.id}/view`,link_id:accountId,download_raw_file:true,include_base64:true});
      if(!Buffer.isBuffer(result?.bytes))throw new Error('Drive raw readback must return verified bytes');
      return {file_id:file.id,account_id:accountId,folder_id:folderId,visibility:'private',download_link:`https://drive.google.com/file/d/${file.id}/view`,bytes:result.bytes};
    },
  };
}
