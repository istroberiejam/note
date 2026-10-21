"""Book imports stream to temporary disk; only bounded extracted text returns."""
import json,os,re,shutil,tempfile,threading,urllib.parse,urllib.request,zipfile
from pathlib import Path
from pypdf import PdfReader
import google_drive

MAX_BYTES=max(1,min(500,int(os.getenv('BOOK_MAX_MB','500'))))*1_000_000
MAX_TEXT=750_000
MAX_PAGES=1000
BUSY=threading.Lock()

def page_range(p):
    def number(key):
        value=p.get(key)
        if value in ('',None):return None
        number=int(value)
        if number<1:raise ValueError('PDF page numbers start at 1.')
        return number
    start,end=number('start'),number('end')
    if start and end and end<start:raise ValueError('The last PDF page must be at least the first page.')
    return start,end

def authorize(handler):
    if google_drive.configured() and not (google_drive.session(handler)[1] or {}).get('access_token'):
        raise ValueError('Connect Google Drive before importing a book on this server.')

def stream(source,target,limit=MAX_BYTES,expected=None):
    total=0
    with open(target,'wb') as out:
        while True:
            block=source.read(min(1024*1024,expected-total) if expected is not None else 1024*1024)
            if not block:break
            total+=len(block)
            if total>limit:raise ValueError(f'Books can be up to {limit//1_000_000} MB.')
            out.write(block)
            if expected is not None and total==expected:break
    if expected is not None and total!=expected:raise ValueError('Book transfer was interrupted. Please retry.')
    if not total:raise ValueError('The book file is empty.')
    return total

def extract_book(path,name,start=None,end=None):
    suffix=Path(name).suffix.lower();pages=[];count=0
    def add(location,text):
        nonlocal count
        count+=len(text)
        if count>MAX_TEXT:raise ValueError('This selection contains too much text for one import. Import a smaller chapter using a PDF page range. No partial notes were added.')
        pages.append({'location':location,'text':text})
    if suffix=='.pdf':
        with open(path,'rb') as file:
            reader=PdfReader(file)
            if reader.is_encrypted:
                if not reader.decrypt(''):raise ValueError('Remove the PDF password before importing this book.')
            total=len(reader.pages);first=start or 1;last=end or total
            if first>total or last>total:raise ValueError(f'This PDF has {total} pages. Choose a range within the book.')
            if last-first+1>MAX_PAGES:raise ValueError('Choose a chapter or page range of at most 1,000 PDF pages per import.')
            for i in range(first-1,last):add(f'Page {i+1}',reader.pages[i].extract_text() or '')
    else:
        if start or end:raise ValueError('Page ranges are supported for PDF books only. Clear the range for DOCX or TXT.')
        if suffix=='.docx':
            with zipfile.ZipFile(path) as archive:
                if sum(x.file_size for x in archive.infolist())>64*1024*1024:raise ValueError('This Word book expands beyond the processing limit. Export a chapter as PDF and import that instead.')
            from server import extract
            for p in extract(name,Path(path).read_bytes()):add(p['location'],p['text'])
        elif suffix in ('.txt','.md'):
            if Path(path).stat().st_size>MAX_TEXT*4:raise ValueError('This text book is too long. Import a smaller chapter.')
            add('Text',Path(path).read_text(encoding='utf-8-sig'))
        else:raise ValueError('Book references support PDF, DOCX, TXT, and Google Docs.')
    if not any(p['text'].strip() for p in pages):raise ValueError('No text found. Scanned book pages need OCR before import.')
    return {'name':name,'pages':pages}

def run(handler,download,name,start=None,end=None):
    if Path(name).suffix.lower() not in ('.pdf','.docx','.txt','.md'):raise ValueError('Book references support PDF, DOCX, TXT, and Google Docs.')
    authorize(handler)
    if not BUSY.acquire(blocking=False):raise ValueError('Another book is being imported. Please wait and try again.')
    try:
        if shutil.disk_usage(tempfile.gettempdir()).free<MAX_BYTES+64*1024*1024:raise ValueError('The server needs more temporary disk space to import a book.')
        with tempfile.TemporaryDirectory(prefix='margin-book-') as folder:
            path=Path(folder)/'book';download(path)
            return extract_book(path,name,start,end)
    finally:BUSY.release()

def upload(handler):
    size=int(handler.headers.get('Content-Length',0))
    if not 0<size<=MAX_BYTES:raise ValueError(f'Books can be up to {MAX_BYTES//1_000_000} MB.')
    name=urllib.parse.unquote(handler.headers.get('X-File-Name','book.pdf'));start,end=page_range({'start':handler.headers.get('X-Page-Start'),'end':handler.headers.get('X-Page-End')})
    return run(handler,lambda path:stream(handler.rfile,path,expected=size),name,start,end)

def drive(handler,p):
    token=google_drive.access_token(handler);fid=p.get('id','')
    if not re.fullmatch(r'[\w-]+',fid,flags=re.ASCII):raise ValueError('Invalid Drive file.')
    start,end=page_range(p);url='https://www.googleapis.com/drive/v3/files/'+fid
    meta=json.loads(google_drive.get(url+'?fields=name,mimeType,size',token));name=meta['name']
    if int(meta.get('size',0))>MAX_BYTES:raise ValueError(f'Books can be up to {MAX_BYTES//1_000_000} MB.')
    native=meta['mimeType']=='application/vnd.google-apps.document'
    if native:
        url+='/export?'+urllib.parse.urlencode({'mimeType':'application/vnd.openxmlformats-officedocument.wordprocessingml.document'});name+='.docx'
    else:url+='?alt=media'
    def download(path):
        req=urllib.request.Request(url,headers={'Authorization':'Bearer '+token})
        with urllib.request.urlopen(req,timeout=120) as r:stream(r,path,expected=None if native else int(meta['size']) if meta.get('size') else None)
    return run(handler,download,name,start,end)
