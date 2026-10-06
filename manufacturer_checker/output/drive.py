"""フォルダID指定のDrive保存。ローカルExcelを保持してからアップロード。"""
from pathlib import Path
DEFAULT_PARENT_FOLDER_ID = ''
FOLDER_MIME = 'application/vnd.google-apps.folder'

def build_colab_drive_service():
    from google.colab import auth
    import google.auth
    from googleapiclient.discovery import build
    auth.authenticate_user()
    credentials, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/drive'])
    return build('drive', 'v3', credentials=credentials, cache_discovery=False)

def validate_parent(service, parent_id):
    if not parent_id:
        raise ValueError("保存先フォルダのURLまたはIDをColab側で設定してください")
    parent = service.files().get(fileId=parent_id, supportsAllDrives=True,
        fields='id,name,mimeType,trashed,driveId,capabilities(canAddChildren)').execute()
    if parent.get('trashed') or parent.get('mimeType') != FOLDER_MIME:
        raise ValueError('保存先は有効なDriveフォルダではありません')
    if not parent.get('capabilities', {}).get('canAddChildren', False):
        raise PermissionError('指定フォルダへの追加権限がありません。ColabのGoogleアカウントを確認してください')
    return parent

def _escape_query(value):
    return value.replace('\\', '\\\\').replace("'", "\\'")

def ensure_manufacturer_folder(service, manufacturer, parent_id=DEFAULT_PARENT_FOLDER_ID):
    name = str(manufacturer).strip()
    if not name or name in ('.', '..'):
        raise ValueError('メーカー名を指定してください')
    parent = validate_parent(service, parent_id)
    query = (f"'{_escape_query(parent_id)}' in parents and trashed = false "
        f"and mimeType = '{FOLDER_MIME}' and name = '{_escape_query(name)}'")
    found, page_token = [], None
    while True:
        options = dict(q=query, spaces='drive', pageSize=100,
            fields='nextPageToken,files(id,name)', supportsAllDrives=True, includeItemsFromAllDrives=True)
        if parent.get('driveId'):
            options.update(corpora='drive', driveId=parent['driveId'])
        if page_token:
            options['pageToken'] = page_token
        page = service.files().list(**options).execute()
        found.extend(page.get('files', []))
        page_token = page.get('nextPageToken')
        if not page_token:
            break
    if len(found) > 1:
        raise ValueError(f'保存先に同名メーカーのフォルダが複数あります: {name}。1つに整理してください')
    if found:
        return found[0]
    return service.files().create(body={'name':name,'mimeType':FOLDER_MIME,'parents':[parent_id]},
        fields='id,name', supportsAllDrives=True).execute()

def upload_result(service, local_path, manufacturer, parent_id=DEFAULT_PARENT_FOLDER_ID, *, media_factory=None):
    path = Path(local_path)
    if not path.is_file():
        raise FileNotFoundError(path)
    folder = ensure_manufacturer_folder(service, manufacturer, parent_id)
    if media_factory is None:
        from googleapiclient.http import MediaFileUpload
        media_factory = MediaFileUpload
    media = media_factory(str(path), mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', resumable=True)
    created = service.files().create(body={'name':path.name,'parents':[folder['id']]},
        media_body=media, fields='id,name,webViewLink,parents,size', supportsAllDrives=True).execute()
    verified = service.files().get(fileId=created['id'], fields='id,name,parents,size,webViewLink', supportsAllDrives=True).execute()
    if folder['id'] not in verified.get('parents', []) or int(verified.get('size', -1)) != path.stat().st_size:
        raise RuntimeError('Drive保存の確認に失敗しました。ローカル結果は保持されています')
    return verified

class DriveSearchCheckpoint:
    """指定メーカーの_stateへ検索状態を復元・同期する。"""
    def __init__(self, service, manufacturer, parent_id, local_path, *, media_factory=None):
        self.service=service
        self.media_factory=media_factory
        manufacturer_folder=ensure_manufacturer_folder(service,manufacturer,parent_id)
        self.folder=ensure_manufacturer_folder(service,'_state',manufacturer_folder['id'])
        self.path=Path(local_path);self.file_id=None
        query=f"'{_escape_query(self.folder['id'])}' in parents and trashed=false and name='name_search_v1.json'"
        found=[];token=None
        while True:
            options=dict(q=query,fields='nextPageToken,files(id,name)',supportsAllDrives=True,includeItemsFromAllDrives=True)
            if token:options['pageToken']=token
            page=service.files().list(**options).execute();found.extend(page.get('files',[]))
            token=page.get('nextPageToken')
            if not token:break
        if len(found)>1:raise ValueError('_state内に同名状態ファイルが複数あります')
        if found:self.file_id=found[0]['id']
    def restore(self):
        if self.file_id:
            data=self.service.files().get_media(fileId=self.file_id,supportsAllDrives=True).execute()
            import json
            json.loads(data)  # 不正JSONでローカル状態を上書きしない。
            self.path.parent.mkdir(parents=True,exist_ok=True)
            temp=self.path.with_suffix('.restore');temp.write_bytes(data);temp.replace(self.path)
        return self.path
    def sync(self,path):
        factory=self.media_factory
        if factory is None:
            from googleapiclient.http import MediaFileUpload
            factory=MediaFileUpload
        media=factory(str(path),mimetype='application/json',resumable=True)
        if self.file_id:
            saved=self.service.files().update(fileId=self.file_id,media_body=media,fields='id,size',supportsAllDrives=True).execute()
        else:
            saved=self.service.files().create(body={'name':'name_search_v1.json','parents':[self.folder['id']]},media_body=media,fields='id,size',supportsAllDrives=True).execute()
            self.file_id=saved['id']
        if int(saved.get('size',-1))!=Path(path).stat().st_size:raise RuntimeError('検索状態のDrive同期を確認できませんでした')
