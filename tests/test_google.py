import io,json,time,unittest,urllib.parse
from unittest.mock import patch
from types import SimpleNamespace
import google_drive as g
class Fake:
 def __init__(self,path,cookie=''): self.path=path;self.headers={'Cookie':cookie};self.headers_out={};self.wfile=io.BytesIO()
 def send_response(self,s):self.status=s
 def send_header(self,k,v):self.headers_out[k]=v
 def end_headers(self):pass
 def send_json(self,obj,status=200):self.status=status;self.result=obj
class GoogleTests(unittest.TestCase):
 def tearDown(self):g.SESSIONS.clear()
 @patch.dict('os.environ',{'GOOGLE_CLIENT_ID':'client','GOOGLE_CLIENT_SECRET':'secret'})
 def test_oauth_state_and_cookie_rotation(self):
  h=Fake('/auth/google');g.oauth_get(h);self.assertEqual(h.status,302)
  self.assertIn('HttpOnly; Secure; SameSite=Lax',h.headers_out['Set-Cookie'])
  cookie=h.headers_out['Set-Cookie'].split(';')[0];sid=cookie.split('=')[1];state=g.SESSIONS[sid]['state']
  bad=Fake('/auth/google/callback?code=test&state=wrong',cookie);g.oauth_get(bad);self.assertEqual(bad.status,400)
  good=Fake('/auth/google/callback?code=test&state='+state,cookie)
  with patch.object(g,'token_request',return_value={'access_token':'token','refresh_token':'refresh'}):g.oauth_get(good)
  self.assertEqual(good.status,302);self.assertNotIn(sid,g.SESSIONS)
  newcookie=good.headers_out['Set-Cookie'].split(';')[0]
  self.assertEqual(g.access_token(Fake('/',newcookie)),'token')
  replay=Fake('/auth/google/callback?code=test&state='+state,cookie);g.oauth_get(replay);self.assertEqual(replay.status,400)
 def test_no_shared_token(self):
  with patch.dict('os.environ',{'GOOGLE_ACCESS_TOKEN':'legacy-shared'}):
   with self.assertRaises(ValueError):g.access_token(Fake('/'))
 def test_refresh(self):
  g.SESSIONS['sid']={'access_token':'old','refresh_token':'refresh','expires':0,'until':time.time()+500}
  with patch.object(g,'token_request',return_value={'access_token':'new','expires_in':3600}) as request:
   self.assertEqual(g.access_token(Fake('/','margin_session=sid')),'new');self.assertEqual(request.call_count,1)
 def test_native_docs_download(self):
  h=Fake('/');responses=[json.dumps({'name':'Lesson','mimeType':'application/vnd.google-apps.document'}).encode(),b'docx']
  with patch.object(g,'access_token',return_value='token'),patch.object(g,'get',side_effect=responses) as download:
   r=g.drive_request(h,'/api/drive/file',{'id':'abc_123'});self.assertEqual(r['name'],'Lesson.docx');self.assertIn('/export?',download.call_args.args[0])
if __name__=='__main__':unittest.main()
