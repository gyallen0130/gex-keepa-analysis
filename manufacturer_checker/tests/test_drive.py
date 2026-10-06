import unittest
import tempfile
from pathlib import Path
from output.drive import ensure_manufacturer_folder, upload_result, FOLDER_MIME
class Request:
 def __init__(self,value):self.value=value
 def execute(self):return self.value
class Service:
 def __init__(self,found=(),writable=True,pages=None):
  self.found=list(found);self.writable=writable;self.created=[];self.pages=iter(pages) if pages else None;self.list_calls=[]
 def files(self):return self
 def get(self,**kw):
  if kw['fileId']=='upload':return Request({'id':'upload','parents':['child'],'size':'3','webViewLink':'verified-link'})
  return Request({'id':'parent','mimeType':FOLDER_MIME,'capabilities':{'canAddChildren':self.writable}})
 def list(self,**kw):
  self.list_calls.append(kw);return Request(next(self.pages) if self.pages else {'files':self.found})
 def create(self,**kw):
  self.created.append(kw);return Request({'id':'upload'} if 'media_body' in kw else {'id':'child','name':kw['body']['name']})
class Tests(unittest.TestCase):
 def test_create_under_requested_parent(self):
  service=Service();folder=ensure_manufacturer_folder(service,'GEX','parent')
  self.assertEqual(folder['id'],'child');self.assertEqual(service.created[0]['body']['parents'],['parent'])
 def test_reuse(self):
  service=Service([{'id':'child','name':'GEX'}]);self.assertEqual(ensure_manufacturer_folder(service,'GEX','parent')['id'],'child');self.assertEqual(service.created,[])
 def test_duplicate_stop_and_pagination(self):
  service=Service(pages=[{'files':[{'id':'1'}],'nextPageToken':'next'},{'files':[{'id':'2'}]}])
  with self.assertRaises(ValueError):ensure_manufacturer_folder(service,'GEX','parent')
  self.assertEqual(service.list_calls[1]['pageToken'],'next');self.assertEqual(service.created,[])
 def test_permission_stop(self):
  service=Service(writable=False)
  with self.assertRaises(PermissionError):ensure_manufacturer_folder(service,'GEX','parent')
  self.assertEqual(service.created,[])
 def test_upload_parent_and_size(self):
  service=Service([{'id':'child','name':'GEX'}])
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'result.xlsx';p.write_bytes(b'123')
   result=upload_result(service,p,'GEX','parent',media_factory=lambda *a,**kw:object())
   self.assertEqual(result['id'],'upload');self.assertEqual(service.created[0]['body']['parents'],['child']);self.assertTrue(p.exists())
 def test_escape_folder_name(self):
  service=Service();ensure_manufacturer_folder(service,"Maker's",'parent')
  self.assertIn("Maker\\'s",service.list_calls[0]['q'])

class CheckpointTests(unittest.TestCase):
 def test_restore_and_update_same_file(self):
  from output.drive import DriveSearchCheckpoint
  class StateService(Service):
   def __init__(self):
    super().__init__(pages=[{'files':[{'id':'maker'}]},{'files':[{'id':'state_folder'}]},{'files':[{'id':'state_file'}]}]);self.updates=[]
   def get_media(self,**kw):return Request(b'{"version":1,"queries":{},"reviews":{}}')
   def update(self,**kw):
    self.updates.append(kw);return Request({'id':'state_file','size':str(self.path.stat().st_size)})
  with tempfile.TemporaryDirectory() as d:
   service=StateService();p=Path(d)/'state.json';service.path=p
   cp=DriveSearchCheckpoint(service,'日仏商事','parent',p,media_factory=lambda *a,**kw:object())
   cp.restore();self.assertTrue(p.exists());cp.sync(p)
   self.assertEqual(service.updates[0]['fileId'],'state_file')
   self.assertEqual(service.created,[])
