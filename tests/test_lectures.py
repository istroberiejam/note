import io,os,shutil,subprocess,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import lectures as l
class Handler:
 def __init__(self,data=b'',**headers):self.rfile=io.BytesIO(data);self.headers=headers
class LectureTests(unittest.TestCase):
 def setUp(self):
  self.env=patch.dict(os.environ,{'OPENAI_API_KEY':'test','HOST':'127.0.0.1'});self.env.start()
  self.auth=patch.object(l,'owner',return_value='owner');self.auth.start()
 def tearDown(self):
  for j in l.JOBS.values():l.clean(j)
  l.JOBS.clear();self.env.stop();self.auth.stop()
 def create(self,name='recording.mp4',size=10):
  with patch.object(l,'ffmpeg',return_value='ffmpeg'),patch.object(l.shutil,'disk_usage',return_value=SimpleNamespace(free=3_000_000_000)):
   return l.create(Handler(),name,size)
 def test_limit_boundary_without_allocating_large_file(self):
  j=self.create(size=1_500_000_000);self.assertEqual(j['size'],1_500_000_000);self.assertFalse(Path(j['path']).exists())
  with self.assertRaisesRegex(ValueError,'1.5 GB'):self.create(size=1_500_000_001)
 def test_disk_requirement(self):
  with patch.object(l,'ffmpeg'),patch.object(l.shutil,'disk_usage',return_value=SimpleNamespace(free=100)):
   with self.assertRaisesRegex(ValueError,'temporary storage'):l.create(Handler(),'lecture.mp4',20)
 def test_chunk_order_and_size(self):
  j=self.create(size=6)
  def chunk(offset,data):return l.append(Handler(data,**{'X-Lecture-Id':j['id'],'X-Upload-Offset':str(offset),'Content-Length':str(len(data))}))
  chunk(0,b'abc');self.assertEqual(j['received'],3)
  with self.assertRaisesRegex(ValueError,'offset'):chunk(0,b'abc')
  with self.assertRaisesRegex(ValueError,'declared'):chunk(3,b'abcdef')
  chunk(3,b'def');self.assertEqual(Path(j['path']).read_bytes(),b'abcdef')
  with patch.object(l,'owner',return_value='another user'):
   with self.assertRaisesRegex(ValueError,'not found'):l.find(Handler(),j['id'])
 def test_cancellation_and_cleanup(self):
  j=self.create();Path(j['path']).write_bytes(b'abc')
  h=Handler();h.path='/api/lecture/cancel';result=l.request(h,{'id':j['id']});self.assertEqual(result['status'],'cancelled');self.assertFalse(Path(j['directory']).exists())
 def test_single_job_and_incomplete_upload(self):
  j=self.create()
  with self.assertRaisesRegex(ValueError,'Another lecture'):self.create()
  h=Handler();h.path='/api/lecture/finish'
  with self.assertRaisesRegex(ValueError,'incomplete'):l.request(h,{'id':j['id']})
 def test_real_audio_segmentation_with_mocked_provider(self):
  j=self.create(name='short.wav',size=1)
  subprocess.run([l.ffmpeg(),'-nostdin','-f','lavfi','-i','sine=frequency=440:duration=1','-y',j['path']],check=True,capture_output=True)
  with patch.object(l,'transcribe',return_value='The teacher explains accuracy.') as provider:l.process(j)
  self.assertEqual(j['status'],'done',j['message']);self.assertIn('[00:00:00',j['text']);self.assertIn('accuracy',j['text']);self.assertEqual(provider.call_count,1);self.assertFalse(Path(j['directory']).exists())
 def test_bundled_ffmpeg_extracts_video_audio(self):
  import imageio_ffmpeg
  binary=imageio_ffmpeg.get_ffmpeg_exe();j=self.create(name='short.mp4',size=1)
  subprocess.run([binary,'-nostdin','-f','lavfi','-i','color=c=black:s=64x64:d=1','-f','lavfi','-i','sine=frequency=440:duration=1','-c:v','mpeg4','-c:a','aac','-shortest','-y',j['path']],check=True,capture_output=True)
  with patch.object(l,'ffmpeg',return_value=binary),patch.object(l,'transcribe',return_value='Video discussion'):l.process(j)
  self.assertEqual(j['status'],'done',j['message']);self.assertIn('Video discussion',j['text'])
 def test_drive_download_streams_bounded_blocks(self):
  import json
  payload=b'x'*(2*1024*1024+11)
  class Response(io.BytesIO):
   def read(self,n=-1):
    if not 0<n<=1024*1024:raise AssertionError('Download must use bounded reads')
    return super().read(n)
  class InlineThread:
   def __init__(self,target,args,daemon):self.target=target;self.args=args
   def start(self):self.target(*self.args)
  meta=json.dumps({'name':'video.mp4','size':str(len(payload)),'mimeType':'video/mp4'}).encode()
  with patch.object(l.google_drive,'access_token',return_value='token'),patch.object(l.google_drive,'get',return_value=meta),patch.object(l.urllib.request,'urlopen',return_value=Response(payload)),patch.object(l.threading,'Thread',InlineThread),patch.object(l,'convert',return_value=[]),patch.object(l,'ffmpeg',return_value='ffmpeg'),patch.object(l.shutil,'disk_usage',return_value=SimpleNamespace(free=3_000_000_000)):
   result=l.start_drive(Handler(),{'id':'video123'})
  self.assertEqual(result['status'],'done');self.assertEqual(result['received'],len(payload))
 def test_failure_keeps_completed_transcript(self):
  j=self.create();parts=[Path(j['directory'])/f'{i}.mp3' for i in range(2)]
  for p in parts:p.write_bytes(b'fake')
  with patch.object(l,'convert',return_value=parts),patch.object(l,'transcribe',side_effect=['First segment',ValueError('Provider unavailable')]):l.process(j)
  self.assertEqual(j['status'],'error');self.assertIn('First segment',j['text']);self.assertFalse(Path(j['directory']).exists())
if __name__=='__main__':unittest.main()
