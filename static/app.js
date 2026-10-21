const $=s=>document.querySelector(s);
let notebooks;
try{notebooks=MarginNotebooks.open(localStorage)}catch(e){$('#notice').hidden=false;$('#notice').textContent=e.message;throw e}
let project=notebooks.get().project,tab='notes';
function activeNotebook(){return notebooks.state.activeId}
function renderSubjects(){
  $('#current-subject').textContent=notebooks.get().name;
  $('#notebook-tabs').replaceChildren();
  for(const n of notebooks.state.notebooks){const b=document.createElement('button');b.textContent=n.name;b.className=n.id===activeNotebook()?'subject selected':'subject';b.setAttribute('aria-pressed',String(n.id===activeNotebook()));b.onclick=()=>{try{notebooks.select(n.id);project=n.project;tab='notes';notice('');renderSubjects();render()}catch(e){notice(e.message)}};$('#notebook-tabs').append(b)}
}
$('#new-notebook').onclick=()=>{$('#notebook-form').reset();$('#notebook-error').textContent='';$('#notebook-dialog').showModal();$('#notebook-name').focus()};
$('#notebook-close').onclick=()=>$('#notebook-dialog').close();
$('#notebook-form').onsubmit=e=>{e.preventDefault();try{const n=notebooks.add($('#notebook-name').value);project=n.project;tab='notes';$('#notebook-dialog').close();renderSubjects();render()}catch(e){$('#notebook-error').textContent=e.message}};
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function notice(s){$('#notice').hidden=!s;$('#notice').textContent=s}
function save(){try{notebooks.persist()}catch{notice('Browser storage is full. Export your notes before closing this page.')}}
async function api(path,body){const r=await fetch('/api/'+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const d=await r.json();if(!r.ok)throw Error(d.error||'Request failed');return d}
function render(){ $('#title').value=project.title;document.querySelectorAll('[data-tab]').forEach(b=>b.classList.toggle('selected',b.dataset.tab===tab));$('#source-list').textContent=project.sources.map(s=>'✓ '+s).join('   ·   ');$('#add').hidden=tab!=='notes';$('#generate').hidden=tab==='references';$('#generate').textContent=tab==='notes'?'✦ Match lecture notes':`✦ Generate 100 ${tab==='quiz'?'quiz':'exam'} items`;$('#view-label').textContent={notes:'YOUR CLASS NOTES',references:'BOOK REFERENCES',quiz:'QUIZ REVIEW',exam:'EXAM REVIEW'}[tab];$('#view-description').textContent={notes:'Original material on the left. The discussion beside it.',references:'Separate chapter notes, with page locations and related concepts.',quiz:'Identification & enumeration. Answers immediately after each item.',exam:'Multiple choice. Answers and option-by-option elimination after each item.'}[tab];
if(tab==='notes')$('#content').innerHTML=project.concepts.length?project.concepts.map(c=>`<article class="concept"><div class="concept-header"><input data-id="${c.id}" data-field="title" aria-label="Concept title" value="${esc(c.title)}"><small>${esc(c.source)}</small><button data-delete="${c.id}" aria-label="Delete concept">×</button></div><div class="columns"><div><div class="label">CLASS MATERIAL · VERBATIM</div><textarea data-id="${c.id}" data-field="text" aria-label="Class material">${esc(c.text)}</textarea></div><div><div class="label">SIDE NOTE/S · LECTURE DISCUSSION</div><textarea data-id="${c.id}" data-field="side" aria-label="Lecture side notes" placeholder="Add the teacher’s explanation, or match an uploaded lecture…">${esc(c.side)}</textarea></div></div></article>`).join(''):'<div class="empty"><small>YOUR IDEAS BELONG HERE</small><h2>A blank page. A clearer mind.</h2><p>Add your first class material to start building your notebook.<br>Every concept gets its own space for the lecture discussion.</p></div>';
else if(tab==='references')$('#content').innerHTML=project.references.length?project.references.map((r,i)=>`<article class="reference"><h3>${esc(r.name)}</h3><p>${esc(r.location)}</p><input data-reference="${i}" data-field="related" aria-label="Related concept" placeholder="Related concept / chapter" value="${esc(r.related)}"><textarea data-reference="${i}" data-field="text" aria-label="Reference notes">${esc(r.text)}</textarea></article>`).join(''):'<div class="empty"><h2>Read a little deeper.</h2><p>Add a book chapter above. Its notes stay separate from your class material.</p></div>';
else $('#content').innerHTML=`<textarea class="review" id="review" aria-label="Review questions" placeholder="Generate a source-grounded review, or write your own questions here…">${esc(project[tab])}</textarea>`;
}
$('#title').oninput=e=>{project.title=e.target.value;save()};document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>{tab=b.dataset.tab;render()});
$('#content').oninput=e=>{const t=e.target;if(t.dataset.id){const c=project.concepts.find(c=>c.id===t.dataset.id);c[t.dataset.field]=t.value}else if(t.dataset.reference!==undefined)project.references[Number(t.dataset.reference)][t.dataset.field]=t.value;else if(t.id==='review')project[tab]=t.value;save()};
$('#content').onclick=e=>{if(e.target.dataset.delete){project.concepts=project.concepts.filter(c=>c.id!==e.target.dataset.delete);save();render()}};
$('#add').onclick=()=>{project.concepts.push({id:crypto.randomUUID(),title:'New concept',text:'',side:'',source:'Manual notes'});save();render()};
async function readFile(file){return new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result.split(',')[1]);r.onerror=reject;r.readAsDataURL(file)})}
function appendPages(notebookId,kind,file,pages){
 const target=notebooks.get(notebookId).project;
 if(kind==='class'){for(const p of pages)target.concepts.push({id:crypto.randomUUID(),title:p.text.split('\n').find(x=>x.trim())?.slice(0,140)||p.location,text:p.text,side:'',source:file.name+' · '+p.location})}
 else if(kind==='book'){for(const p of pages)target.references.push({name:file.name,location:p.location,text:p.text,related:''})}
 else target.lectures.push({name:file.name,text:pages.map(p=>p.text).join('\n')});
 const label={class:'Learning material',book:'Book reference',lecture:'Lecture'}[kind];target.sources.push(label+' · '+file.name);
 save();if(activeNotebook()===notebookId){tab=kind==='book'?'references':'notes';render()}
 notice(label+' imported into '+notebooks.get(notebookId).name+'.');
}
async function importFile(file,kind,notebookId){
 if(kind==='lecture'&&!file.name.toLowerCase().endsWith('.txt')){await uploadLecture(file,notebookId);return}
 if(file.size>28*1024*1024)throw Error('Documents and text transcripts must be under 28 MB. Lecture video/audio supports up to 1.5 GB.');
 notice('Processing '+file.name+' for '+notebooks.get(notebookId).name+'…');
 const pages=(await api('extract',{name:file.name,data:await readFile(file)})).pages;appendPages(notebookId,kind,file,pages);
}
for(const [id,kind] of [['class-file','class'],['lecture-file','lecture'],['book-file','book']])$('#'+id).onchange=async e=>{
 const file=e.target.files[0],notebookId=activeNotebook();if(!file)return;
 try{await importFile(file,kind,notebookId)}catch(err){notice(err.message)}finally{e.target.value=''}
};
$('#generate').onclick=async()=>{const notebookId=activeNotebook(),target=notebooks.get(notebookId).project;const kind=tab==='notes'?'side':tab;if(!project.concepts.some(c=>c.text.trim()))return notice('Add class materials first.');if(kind==='side'&&!project.lectures.length)return notice('Add a lecture recording or transcript first.');if(!confirm('Send this notebook to OpenAI to '+(kind==='side'?'match lecture discussion':'generate review questions')+'?'))return;$('#generate').disabled=true;notice('Working with your sources. This may take a few minutes…');try{const d=await api('generate',{kind,project:target});if(kind==='side'){const map=JSON.parse(d.text.replace(/^```(?:json)?\s*/,'').replace(/\s*```$/,''));for(const c of target.concepts)if(typeof map[c.id]==='string')c.side=map[c.id]}else target[kind]=d.text;save();render();notice('Draft generated for '+notebooks.get(notebookId).name+'. Check source coverage and answers before studying.')}catch(e){notice(e.message)}finally{$('#generate').disabled=false}};
$('#export').onclick=async()=>{const exportTitle=project.title;try{const d=await api('export',project);const bytes=Uint8Array.from(atob(d.data),c=>c.charCodeAt(0));const u=URL.createObjectURL(new Blob([bytes],{type:'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}));const a=document.createElement('a');a.href=u;a.download=(exportTitle||'Class notes')+'.docx';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);notice('Word document exported. Upload it to Google Drive and open with Google Docs; direct Google export creates separate document tabs.')}catch(e){notice(e.message)}};
$('#google').onclick=async()=>{if(!confirm('Create a Google document containing this notebook?'))return;try{notice('Creating Google Docs tabs…');const d=await api('google',project);notice('Google document created. ');const a=document.createElement('a');a.href=d.url;a.textContent='Open Google Docs ↗';a.target='_blank';a.rel='noopener';$('#notice').append(a)}catch(e){notice(e.message)}};
$('#reset').onclick=()=>{if(confirm('Clear only '+notebooks.get().name+'? Export first to keep a copy. Other subjects will remain unchanged.')){project=notebooks.clear().project;tab='notes';render();notice('This notebook was cleared.')}};
renderSubjects();save();
fetch('/api/status').then(r=>r.json()).then(d=>{
$('#connections').textContent=`AI: ${d.ai?'configured':'not configured'}. Google Drive: ${d.google?'connected':d.googleConfigured?'ready to connect':'not configured'}.`;
$('.connect').textContent=d.google?'Reconnect Google Drive':'Connect Google Drive';
$('#disconnect').hidden=!d.google;
});render();
let nextDrivePage='',driveContext=null;
const categoryName={class:'Learning materials',book:'Book references',lecture:'Lecture recordings'};
function suitableDriveFile(file,kind){
 const ext=file.name.toLowerCase().split('.').pop();
 if(kind==='lecture')return ['mp3','mp4','wav','m4a','mov','webm','mkv','txt'].includes(ext);
 return ['pdf','pptx','docx','txt','md'].includes(ext)||['application/vnd.google-apps.document','application/vnd.google-apps.presentation'].includes(file.mimeType);
}
async function listDrive(more=false){const context=driveContext;try{
 const d=await api('drive/list',{search:$('#drive-search').value,pageToken:more?nextDrivePage:''});if(context!==driveContext)return;
 if(!more)$('#drive-files').replaceChildren();
 for(const file of d.files||[]){if(file.mimeType==='application/vnd.google-apps.folder')continue;const b=document.createElement('button');b.className='drive-file';b.textContent=file.name;b.disabled=!suitableDriveFile(file,context.kind);if(b.disabled)b.title='Choose a supported '+categoryName[context.kind].toLowerCase()+' file';b.onclick=()=>importDrive(file,context);$('#drive-files').append(b)}
 nextDrivePage=d.nextPageToken||'';$('#drive-more').hidden=!nextDrivePage;if(!$('#drive-files').children.length)$('#drive-files').textContent='No files found.';
 }catch(e){notice(e.message);$('#drive-dialog').close()}}
document.querySelectorAll('[data-drive-kind]').forEach(b=>b.onclick=()=>{
 driveContext={kind:b.dataset.driveKind,notebookId:activeNotebook()};nextDrivePage='';$('#drive-search').value='';$('#drive-files').textContent='Loading…';$('#drive-category').textContent='Import into '+notebooks.get().name+' → '+categoryName[driveContext.kind];$('#drive-dialog').showModal();listDrive();
});
$('#drive-find').onclick=()=>listDrive();$('#drive-more').onclick=()=>listDrive(true);$('#drive-close').onclick=()=>$('#drive-dialog').close();
async function importDrive(file,context){const {kind,notebookId}=context;$('#drive-dialog').close();notice('Downloading '+file.name+' from Drive…');try{
 if(kind==='lecture'&&!file.name.toLowerCase().endsWith('.txt')){await driveLecture(file,notebookId);return}
 const downloaded=await api('drive/file',{id:file.id});const bytes=Uint8Array.from(atob(downloaded.data),c=>c.charCodeAt(0));await importFile(new File([bytes],downloaded.name),kind,notebookId);
 }catch(e){notice(e.message)}}
$('#disconnect').onclick=async()=>{try{await api('google/disconnect',{});location.reload()}catch(e){notice(e.message)}};

const LECTURE_LIMIT=1500000000, UPLOAD_CHUNK=4*1024*1024;
let activeLecture='', lectureNotebookId=activeNotebook(), pollTimer=null;
function showLecture(j){$('#lecture-progress').hidden=false;$('#lecture-name').textContent=j.name;$('#lecture-status').textContent=j.message;const m=$('#lecture-meter');if(['uploading','downloading'].includes(j.status))m.value=100*j.received/j.size;else if(j.status==='done')m.value=100;else m.removeAttribute('value');$('#lecture-cancel').hidden=['done','error','cancelled'].includes(j.status)}
function rememberLecture(j,notebookId){activeLecture=j.id;lectureNotebookId=notebookId;sessionStorage.setItem('margin-lecture-notebook',notebookId);sessionStorage.setItem('margin-lecture-job',j.id);showLecture(j)}
function storeTranscript(j){if(!j.text)return;const target=notebooks.get(lectureNotebookId).project;target.lectures.push({name:j.name,text:j.text});target.sources.push('Lecture · '+j.name);save();if(activeNotebook()===lectureNotebookId)render()}
async function pollLecture(){if(!activeLecture)return;try{const j=await api('lecture/status',{id:activeLecture});showLecture(j);if(['done','error','cancelled'].includes(j.status)){storeTranscript(j);sessionStorage.removeItem('margin-lecture-job');activeLecture='';notice(j.status==='done'?'Lecture imported into '+notebooks.get(lectureNotebookId).name+'. Use “Match lecture notes” to attach discussion to concepts.':j.message+(j.text?' Completed transcript segments have been saved.':''));return}}catch(e){notice(e.message+' If the server restarted, start the import again.');return}pollTimer=setTimeout(pollLecture,4000)}
async function uploadLecture(file,notebookId){if(activeLecture)throw Error('A lecture is already processing. Wait or cancel it first.');if(file.size>LECTURE_LIMIT)throw Error('Lecture recordings can be up to 1.5 GB (1,500,000,000 bytes).');if(!confirm('Transcribe this lecture using OpenAI? Audio will be split into 10-minute segments. Usage charges depend on lecture duration.'))return;const j=await api('lecture/create',{name:file.name,size:file.size});rememberLecture(j,notebookId);try{for(let offset=0;offset<file.size;offset+=UPLOAD_CHUNK){if(activeLecture!==j.id)return;const r=await fetch('/api/lecture/chunk',{method:'POST',headers:{'Content-Type':'application/octet-stream','X-Lecture-Id':j.id,'X-Upload-Offset':String(offset)},body:file.slice(offset,offset+UPLOAD_CHUNK)});const d=await r.json();if(!r.ok)throw Error(d.error||'Upload failed');showLecture(d)}if(activeLecture!==j.id)return;showLecture(await api('lecture/finish',{id:j.id}));pollLecture()}catch(e){try{await api('lecture/cancel',{id:j.id})}catch{}activeLecture='';sessionStorage.removeItem('margin-lecture-job');$('#lecture-progress').hidden=true;throw e}}
async function driveLecture(file,notebookId){if(activeLecture)throw Error('A lecture is already processing. Wait or cancel it first.');if(Number(file.size)>LECTURE_LIMIT)throw Error('Lecture recordings can be up to 1.5 GB.');if(!confirm('Download this lecture from Drive and send its audio to OpenAI for transcription? Usage charges depend on duration.'))return;const j=await api('lecture/drive',{id:file.id});rememberLecture(j,notebookId);pollLecture()}
$('#lecture-cancel').onclick=async()=>{if(!activeLecture)return;try{const j=await api('lecture/cancel',{id:activeLecture});showLecture(j);clearTimeout(pollTimer);if(j.status==='cancelled'){activeLecture='';sessionStorage.removeItem('margin-lecture-job')}else{notice('Cancelling after the current operation finishes…');pollTimer=setTimeout(pollLecture,4000)}}catch(e){notice(e.message)}};
try{const saved=sessionStorage.getItem('margin-lecture-job');if(saved){lectureNotebookId=sessionStorage.getItem('margin-lecture-notebook')||activeNotebook();activeLecture=saved;api('lecture/status',{id:saved}).then(j=>{if(j.status==='uploading'){notice('The upload was interrupted by a page reload. Cancel it, then select the file again.');showLecture(j)}else pollLecture()}).catch(e=>{activeLecture='';sessionStorage.removeItem('margin-lecture-job');notice(e.message)})}}catch{}

document.querySelectorAll('[data-device-file]').forEach(b=>b.onclick=()=>$('#'+b.dataset.deviceFile).click());
