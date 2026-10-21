import io,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from pypdf import PdfWriter
import books
class BooksTests(unittest.TestCase):
 def test_bounded_stream_and_overflow(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'book';self.assertEqual(books.stream(io.BytesIO(b'abcd'),path,limit=4),4);self.assertEqual(path.read_bytes(),b'abcd')
   with self.assertRaisesRegex(ValueError,'up to'):books.stream(io.BytesIO(b'abcde'),path,limit=4)
   with self.assertRaisesRegex(ValueError,'interrupted'):books.stream(io.BytesIO(b'abc'),path,expected=4)
 def test_page_range_validation(self):
  self.assertEqual(books.page_range({'start':'5','end':'20'}),(5,20))
  for p in [{'start':0},{'start':20,'end':5},{'end':-1}]:
   with self.assertRaises(ValueError):books.page_range(p)
 def test_pdf_chapter_locations_and_text_limit(self):
  class Page:
   def extract_text(self):return 'Verbatim chapter content'
  class Reader:
   is_encrypted=False;pages=[Page() for i in range(8)]
  with tempfile.NamedTemporaryFile() as path,patch.object(books,'PdfReader',return_value=Reader()):
   pages=books.extract_book(path.name,'book.pdf',3,5)['pages'];self.assertEqual([p['location'] for p in pages],['Page 3','Page 4','Page 5']);self.assertEqual(pages[0]['text'],'Verbatim chapter content')
   with self.assertRaisesRegex(ValueError,'8 pages'):books.extract_book(path.name,'book.pdf',9,10)
   with patch.object(books,'MAX_TEXT',5):
    with self.assertRaisesRegex(ValueError,'No partial'):books.extract_book(path.name,'book.pdf',1,1)
 def test_txt_and_cleanup(self):
  class Handler:pass
  locations=[]
  def download(path):locations.append(path);path.write_text('Reference material',encoding='utf-8')
  with patch.object(books,'authorize'),patch.object(books.shutil,'disk_usage',return_value=type('Disk',(),{'free':10**10})()):
   self.assertEqual(books.run(Handler(),download,'book.txt')['pages'][0]['text'],'Reference material')
   self.assertFalse(locations[0].exists())
 def test_upload_file_size_boundary(self):
  class Handler:headers={'Content-Length':str(books.MAX_BYTES),'X-File-Name':'Book.pdf'};rfile=io.BytesIO()
  with patch.object(books,'run',return_value={'pages':[]}) as run:books.upload(Handler());self.assertEqual(run.call_count,1)
  Handler.headers={'Content-Length':str(books.MAX_BYTES+1)}
  with self.assertRaisesRegex(ValueError,'up to'):books.upload(Handler())
 def test_drive_book_limit_is_independent_and_streamed(self):
  import json
  meta={'name':'Textbook.pdf','mimeType':'application/pdf','size':'50000000'}
  class Handler:pass
  with patch.object(books.google_drive,'access_token',return_value='token'),patch.object(books.google_drive,'get',return_value=json.dumps(meta).encode()),patch.object(books,'run',return_value={'pages':[]}) as run:
   books.drive(Handler(),{'id':'book123'});self.assertEqual(run.call_args.args[2],'Textbook.pdf')
  meta['size']=str(books.MAX_BYTES+1)
  with patch.object(books.google_drive,'access_token',return_value='token'),patch.object(books.google_drive,'get',return_value=json.dumps(meta).encode()):
   with self.assertRaisesRegex(ValueError,'up to'):books.drive(Handler(),{'id':'book123'})
if __name__=='__main__':unittest.main()
