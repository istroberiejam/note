"""Server-side Google OAuth sessions. Tokens never enter browser JavaScript."""
import json, os, secrets, time, threading, urllib.parse, urllib.request
from http.cookies import SimpleCookie

SESSIONS = {}
LOCK = threading.RLock()
BASE = os.getenv('APP_URL', os.getenv('RENDER_EXTERNAL_URL', 'https://margin-t56k.onrender.com')).rstrip('/')
SCOPES = 'https://www.googleapis.com/auth/drive.readonly https://www.googleapis.com/auth/drive.file'

def configured(): return bool(os.getenv('GOOGLE_CLIENT_ID') and os.getenv('GOOGLE_CLIENT_SECRET'))
def session(handler):
    cookie = SimpleCookie()
    try: cookie.load(handler.headers.get('Cookie', '')); sid = cookie['margin_session'].value
    except (KeyError, ValueError): return None, None
    with LOCK:
        entry = SESSIONS.get(sid)
        if entry and entry['until'] > time.time(): return sid, entry
        SESSIONS.pop(sid, None)
    return None, None

def token_request(fields):
    fields.update(client_id=os.environ['GOOGLE_CLIENT_ID'], client_secret=os.environ['GOOGLE_CLIENT_SECRET'])
    req = urllib.request.Request('https://oauth2.googleapis.com/token', data=urllib.parse.urlencode(fields).encode())
    with urllib.request.urlopen(req, timeout=30) as r: return json.load(r)

def access_token(handler):
    sid, entry = session(handler)
    if not entry or not entry.get('access_token'): raise ValueError('Connect Google Drive first. You may need to reconnect after a server restart.')
    with LOCK:
        if entry['expires'] < time.time()+60:
            if not entry.get('refresh_token'): raise ValueError('Your Google session expired. Reconnect Google Drive.')
            result = token_request({'grant_type':'refresh_token', 'refresh_token':entry['refresh_token']})
            entry.update(access_token=result['access_token'], expires=time.time()+result.get('expires_in',3600))
        return entry['access_token']

def oauth_get(handler):
    parsed = urllib.parse.urlsplit(handler.path)
    if parsed.path not in ('/auth/google', '/auth/google/callback'): return False
    if not configured(): handler.send_json({'error':'Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in Render first.'},400); return True
    if parsed.path == '/auth/google':
        sid, entry = session(handler)
        with LOCK:
            for key in list(SESSIONS):
                if SESSIONS[key]['until'] < time.time(): del SESSIONS[key]
            if len(SESSIONS)>1000: handler.send_json({'error':'Too many sessions. Try later.'},503); return True
            sid = sid or secrets.token_urlsafe(32); state=secrets.token_urlsafe(32)
            SESSIONS[sid] = {'state':state,'until':time.time()+600}
        query = urllib.parse.urlencode({'client_id':os.environ['GOOGLE_CLIENT_ID'],'redirect_uri':BASE+'/auth/google/callback','response_type':'code','scope':SCOPES,'access_type':'offline','prompt':'consent','state':state})
        handler.send_response(302);handler.send_header('Location','https://accounts.google.com/o/oauth2/v2/auth?'+query)
        handler.send_header('Set-Cookie',f'margin_session={sid}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=604800');handler.end_headers();return True
    sid,entry=session(handler);q=urllib.parse.parse_qs(parsed.query)
    if not entry or not secrets.compare_digest(q.get('state',[''])[0],entry.get('state','invalid')):
        handler.send_json({'error':'Google sign-in expired or state was invalid. Please reconnect.'},400);return True
    with LOCK: state=entry.pop('state',None)
    if not state or 'error' in q or not q.get('code'):
        handler.send_json({'error':'Google connection cancelled. Return to Margin and try again.'},400);return True
    try:
        result=token_request({'grant_type':'authorization_code','code':q['code'][0],'redirect_uri':BASE+'/auth/google/callback'})
        # Rotate the cookie after authentication to prevent session fixation.
        fresh=secrets.token_urlsafe(32)
        with LOCK:
            SESSIONS.pop(sid,None)
            SESSIONS[fresh]={'access_token':result['access_token'],'refresh_token':result.get('refresh_token'),'expires':time.time()+result.get('expires_in',3600),'until':time.time()+604800}
        handler.send_response(302);handler.send_header('Location','/?google=connected');handler.send_header('Set-Cookie',f'margin_session={fresh}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=604800');handler.end_headers()
    except Exception: handler.send_json({'error':'Google sign-in failed. Check the client credentials and exact redirect URI in Google Cloud.'},400)
    return True

def get(url, token, limit=None):
    req=urllib.request.Request(url,headers={'Authorization':'Bearer '+token})
    with urllib.request.urlopen(req,timeout=90) as r:
        data=r.read(limit+1 if limit else -1)
    if limit and len(data)>limit: raise ValueError('Drive file is too large. Import files under 24 MB.')
    return data

def drive_request(handler, path, p):
    token=access_token(handler)
    if path=='/api/drive/list':
        query="trashed = false"
        search=p.get('search','').strip()[:150]
        if search: query += " and name contains '"+search.replace('\\','\\\\').replace("'","\\'")+"'"
        params={'q':query,'pageSize':50,'fields':'nextPageToken,files(id,name,mimeType,size)','orderBy':'modifiedTime desc'}
        if p.get('pageToken'): params['pageToken']=p['pageToken']
        return json.loads(get('https://www.googleapis.com/drive/v3/files?'+urllib.parse.urlencode(params),token))
    fid=p.get('id','')
    if not fid or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in fid): raise ValueError('Invalid Drive file.')
    url='https://www.googleapis.com/drive/v3/files/'+fid
    meta=json.loads(get(url+'?fields=id,name,mimeType,size',token))
    if int(meta.get('size',0))>24*1024*1024: raise ValueError('Documents must be smaller than 24 MB. For video/audio up to 1.5 GB, choose Lecture recording / transcript before importing.')
    conversions={'application/vnd.google-apps.document':('application/vnd.openxmlformats-officedocument.wordprocessingml.document','.docx'),'application/vnd.google-apps.presentation':('application/vnd.openxmlformats-officedocument.presentationml.presentation','.pptx')}
    if meta['mimeType'] in conversions:
        mime,ext=conversions[meta['mimeType']]; url+='/export?'+urllib.parse.urlencode({'mimeType':mime});name=meta['name']+ext
    else: url+='?alt=media'; name=meta['name']
    data=get(url,token,24*1024*1024)
    import base64
    return {'name':name,'data':base64.b64encode(data).decode()}
