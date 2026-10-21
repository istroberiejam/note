"""Bounded-disk lecture jobs; video bytes never travel in JSON or base64."""
import io, json, os, re, secrets, shutil, subprocess, tempfile, threading, time
import urllib.request, urllib.error
from pathlib import Path
import google_drive

MAX_BYTES = 1_500_000_000  # 1.5 decimal GB
CHUNK_BYTES = 4 * 1024 * 1024
MAX_SECONDS = 12 * 3600
JOBS = {}
LOCK = threading.RLock()
MEDIA = {'.mp4', '.mp3', '.m4a', '.wav', '.mov', '.webm', '.mkv'}

def ffmpeg():
    found = shutil.which('ffmpeg')
    if found: return found
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()

def owner(handler):
    if google_drive.configured():
        sid, entry = google_drive.session(handler)
        if not entry or not entry.get('access_token'): raise ValueError('Connect Google Drive before uploading a lecture.')
        return sid
    if os.getenv('HOST', '127.0.0.1') not in ('127.0.0.1', 'localhost'):
        raise ValueError('Configure Google sign-in before enabling lecture processing on a public server.')
    return 'local'

def clean(job):
    shutil.rmtree(job['directory'], ignore_errors=True)

def reap():
    with LOCK:
        now = time.time()
        for jid, j in list(JOBS.items()):
            if j['status']=='uploading' and now-j['updated']>1800:
                j.update(status='error', message='Upload expired. Please start again.'); clean(j)
            if j['status'] in ('done', 'error', 'cancelled') and now-j['updated']>21600:
                clean(j); del JOBS[jid]

def create(handler, name, size):
    who = owner(handler)
    if not os.getenv('OPENAI_API_KEY'): raise ValueError('Lecture transcription needs OPENAI_API_KEY in Render Environment. Add it securely before uploading.')
    size = int(size)
    if size <= 0 or size > MAX_BYTES: raise ValueError('Lecture recordings must be between 1 byte and 1.5 GB.')
    ext = Path(name).suffix.lower()
    if ext not in MEDIA: raise ValueError('Choose MP4, MP3, M4A, WAV, MOV, WEBM or MKV.')
    ffmpeg()  # Fail before transferring a large file if the decoder is unavailable.
    reap()
    with LOCK:
        if any(j['status'] not in ('done','error','cancelled') for j in JOBS.values()):
            raise ValueError('Another lecture is processing. Please wait for it to finish.')
        if shutil.disk_usage(tempfile.gettempdir()).free < size + 512*1024*1024:
            raise ValueError('The server needs more temporary storage for this recording. Free space or upgrade the Render service, then retry.')
        directory = tempfile.mkdtemp(prefix='margin-lecture-')
        jid = secrets.token_urlsafe(24)
        j = {'id':jid,'owner':who,'name':str(name)[:250],'size':size,'received':0,'status':'uploading','message':'Waiting for upload','updated':time.time(),'directory':directory,'path':str(Path(directory)/('source'+ext)),'text':'','cancel':threading.Event()}
        JOBS[jid]=j
        return j

def find(handler, jid):
    who = owner(handler)
    with LOCK:
        j=JOBS.get(jid)
        if not j or j['owner'] != who: raise ValueError('Lecture job not found. A server restart or Google reconnection requires a new upload.')
        return j

def public(j):
    with LOCK: return {k:j[k] for k in ('id','name','size','received','status','message','text')}

def update(j, **fields):
    with LOCK: j.update(**fields, updated=time.time())

def check(j):
    if j['cancel'].is_set(): raise ValueError('Lecture cancelled.')

def append(handler):
    jid=handler.headers.get('X-Lecture-Id',''); j=find(handler,jid)
    n=int(handler.headers.get('Content-Length',0)); offset=int(handler.headers.get('X-Upload-Offset','-1'))
    if not 0<n<=CHUNK_BYTES: raise ValueError('Upload chunks must be at most 4 MiB.')
    with LOCK:
        if j['status']!='uploading' or offset!=j['received']: raise ValueError('Upload offset mismatch. Please start the upload again.')
        if offset+n>j['size']: raise ValueError('Upload exceeds the declared file size.')
        data=handler.rfile.read(n)
        if len(data)!=n: raise ValueError('Upload interrupted. Please retry.')
        with open(j['path'],'ab') as out: out.write(data)
        update(j, received=offset+n, message=f'Uploading: {round(100*(offset+n)/j["size"])}%')
    return public(j)

def transcribe(part, key):
    boundary=secrets.token_hex(16)
    header=(f'--{boundary}\r\nContent-Disposition: form-data; name="model"\r\n\r\nwhisper-1\r\n--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="part.mp3"\r\nContent-Type: audio/mpeg\r\n\r\n').encode()
    data=part.read_bytes()
    if len(data)>24*1024*1024: raise ValueError('An audio segment exceeded the transcription limit.')
    req=urllib.request.Request('https://api.openai.com/v1/audio/transcriptions',data=header+data+f'\r\n--{boundary}--\r\n'.encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'multipart/form-data; boundary='+boundary})
    with urllib.request.urlopen(req,timeout=240) as r: return json.load(r)['text']

def convert(j):
    binary=ffmpeg(); path=j['path']
    input_args=['-protocol_whitelist','file,pipe','-format_whitelist','mov,mp3,wav,matroska,webm,aac','-i',path]
    probe=subprocess.run([binary,'-hide_banner',*input_args],capture_output=True,text=True,timeout=30)
    match=re.search(r'Duration: (\d+):(\d+):([\d.]+)',probe.stderr)
    if not match: raise ValueError('Could not read the recording duration. The file may be incomplete or unsupported.')
    h,m,s=map(float,match.groups())
    if h*3600+m*60+s>MAX_SECONDS: raise ValueError('This recording exceeds the 12-hour processing limit. Split it into shorter lectures.')
    output=str(Path(j['directory'])/'part-%04d.mp3'); log=Path(j['directory'])/'conversion.log'
    with log.open('wb') as err:
        proc=subprocess.Popen([binary,'-nostdin','-hide_banner','-loglevel','error','-threads','1',*input_args,'-map','0:a:0','-vn','-ac','1','-ar','16000','-c:a','libmp3lame','-b:a','64k','-f','segment','-segment_time','600',output],stdout=subprocess.DEVNULL,stderr=err)
        start=time.monotonic()
        while proc.poll() is None:
            if j['cancel'].wait(.5) or time.monotonic()-start>7200:
                proc.kill();proc.wait();raise ValueError('Lecture cancelled or audio conversion timed out.')
        if proc.returncode: raise ValueError('Could not decode audio. Ensure the video contains a supported audio track.')
    parts=sorted(Path(j['directory']).glob('part-*.mp3'))
    if not parts: raise ValueError('No audio was found in this recording.')
    Path(path).unlink(missing_ok=True)
    return parts

def process(j, download=None):
    try:
        if download: download()
        check(j);update(j,status='converting',message='Extracting audio and splitting into 10-minute segments…')
        parts=convert(j);texts=[]
        for i,part in enumerate(parts):
            check(j);update(j,status='transcribing',message=f'Transcribing segment {i+1} of {len(parts)}…')
            text=transcribe(part,os.environ['OPENAI_API_KEY']);minutes=i*10
            texts.append(f'[{minutes//60:02d}:{minutes%60:02d}:00 — segment start]\n{text}')
            update(j,text='\n\n'.join(texts));part.unlink()
        check(j);update(j,status='done',message='Lecture transcript ready.')
    except urllib.error.HTTPError as e: update(j,status='error',message=f'Provider returned HTTP {e.code}. Check API quota, permissions, or reconnect Google Drive. Completed segments are available below.')
    except Exception as e: update(j,status='cancelled' if j['cancel'].is_set() else 'error',message=str(e))
    finally: clean(j)

def start_drive(handler,p):
    token=google_drive.access_token(handler);fid=p.get('id','')
    if not re.fullmatch(r'[\w-]+',fid,flags=re.ASCII): raise ValueError('Invalid Drive file.')
    url='https://www.googleapis.com/drive/v3/files/'+fid
    meta=json.loads(google_drive.get(url+'?fields=name,size,mimeType',token))
    j=create(handler,meta['name'],meta.get('size',0));update(j,status='downloading',message='Downloading recording from Google Drive…')
    def download():
        req=urllib.request.Request(url+'?alt=media',headers={'Authorization':'Bearer '+token})
        with urllib.request.urlopen(req,timeout=120) as r, open(j['path'],'wb') as out:
            count=0
            while True:
                check(j);block=r.read(1024*1024)
                if not block: break
                count+=len(block)
                if count>j['size'] or count>MAX_BYTES: raise ValueError('Drive file size changed or exceeds 1.5 GB.')
                out.write(block);update(j,received=count,message=f'Downloading from Drive: {round(count/j["size"]*100)}%')
            if count!=j['size']: raise ValueError('Drive download was incomplete. Please retry.')
    threading.Thread(target=process,args=(j,download),daemon=True).start();return public(j)

def request(handler,p):
    path=handler.path
    if path=='/api/lecture/create': return public(create(handler,p['name'],p['size']))
    if path=='/api/lecture/drive': return start_drive(handler,p)
    reap();j=find(handler,p.get('id',''))
    if path=='/api/lecture/status': return public(j)
    if path=='/api/lecture/cancel':
        with LOCK:
            j['cancel'].set()
            if j['status']=='uploading': update(j,status='cancelled',message='Upload cancelled.');clean(j)
        return public(j)
    if path=='/api/lecture/finish':
        with LOCK:
            if j['status']!='uploading' or j['received']!=j['size']: raise ValueError('Upload is incomplete.')
            update(j,status='queued',message='Preparing audio…')
        threading.Thread(target=process,args=(j,),daemon=True).start();return public(j)
    raise ValueError('Unknown lecture operation.')

def sweeper():
    while True:
        time.sleep(60);reap()
threading.Thread(target=sweeper,daemon=True).start()
