const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const assert=require('node:assert/strict');
const path=require('node:path');
(async()=>{
 const server=spawn(path.resolve('.venv/bin/python'),['server.py'],{env:{...process.env,PORT:'8137',HOST:'127.0.0.1'},stdio:'ignore'});
 let browser;
 try{
  for(let i=0;i<40;i++){try{await fetch('http://127.0.0.1:8137/api/status');break}catch{await new Promise(r=>setTimeout(r,100))}}
  browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH||(require('node:fs').existsSync('/usr/bin/chromium')?'/usr/bin/chromium':undefined)});
  const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/api/status',r=>r.fulfill({json:{google:true,googleConfigured:true,ai:true}}));
  await page.route('**/api/drive/list',r=>r.fulfill({json:{files:[{id:'pdf',name:'Lesson.pdf',mimeType:'application/pdf'},{id:'video',name:'Lecture.mp4',mimeType:'video/mp4'}]}}));
  await page.route('**/api/drive/file',r=>r.fulfill({json:{name:'Lesson.pdf',data:Buffer.from('sample').toString('base64')}}));
  let releaseImport,holdImport=false;
  await page.route('**/api/extract',async r=>{if(holdImport)await new Promise(resolve=>releaseImport=resolve);await r.fulfill({json:{pages:[{location:'Page 1',text:'Exact original learning material'}]}})});
  await page.goto('http://127.0.0.1:8137');
  assert.equal(await page.locator('#notebook-tabs button').count(),4);
  for(const [kind,label] of [['class','Learning materials'],['lecture','Lecture recordings'],['book','Book references']]){
   await page.locator(`[data-drive-kind="${kind}"]`).click();await page.locator('.drive-file').first().waitFor();assert((await page.locator('#drive-category').textContent()).includes(label));
   if(kind==='lecture')assert.equal(await page.getByRole('button',{name:'Lesson.pdf',exact:true}).isDisabled(),true);
   await page.locator('#drive-close').click();
  }
  // Import started in Microscopy must stay there even after switching subjects.
  holdImport=true;await page.locator('[data-drive-kind="class"]').click();await page.getByRole('button',{name:'Lesson.pdf',exact:true}).click();
  for(let i=0;i<50&&!releaseImport;i++)await page.waitForTimeout(20);
  await page.getByRole('button',{name:'Clinical Chemistry',exact:true}).click();releaseImport();
  await page.waitForFunction(()=>document.querySelector('#notice').textContent.includes('imported into Clinical Microscopy'));
  assert.equal(await page.locator('.concept').count(),0);
  await page.getByRole('button',{name:'Clinical Microscopy',exact:true}).click();assert.equal(await page.locator('.concept').count(),1);
  assert.equal(await page.locator('[aria-label="Class material"]').inputValue(),'Exact original learning material');
  // References have their own category and do not become class notes.
  holdImport=false;await page.locator('[data-drive-kind="book"]').click();await page.getByRole('button',{name:'Lesson.pdf',exact:true}).click();await page.locator('.reference').waitFor();assert.equal(await page.locator('.reference').count(),1);
  // Adding subjects and reloading keeps their notes separate.
  await page.locator('#new-notebook').click();await page.locator('#notebook-name').fill('Clinical Immunology');await page.getByRole('button',{name:'Create notebook',exact:true}).click();
  await page.locator('#add').click();await page.locator('[aria-label="Class material"]').fill('Immunology notes');await page.reload();assert.equal(await page.locator('[aria-label="Class material"]').inputValue(),'Immunology notes');
  await page.getByRole('button',{name:'Clinical Microscopy',exact:true}).click();assert.equal(await page.locator('[aria-label="Class material"]').inputValue(),'Exact original learning material');
  // A completed video goes into its starting notebook, even when another is open.
  page.on('dialog',d=>d.accept());let complete=false;
  await page.route('**/api/lecture/drive',r=>r.fulfill({json:{id:'test-job',name:'Lecture.mp4',size:100,received:100,status:'transcribing',message:'Processing',text:''}}));
  await page.route('**/api/lecture/status',r=>r.fulfill({json:{id:'test-job',name:'Lecture.mp4',size:100,received:100,status:complete?'done':'transcribing',message:'Processing',text:complete?'Microscopy lecture transcript':''}}));
  await page.locator('[data-drive-kind="lecture"]').click();await page.getByRole('button',{name:'Lecture.mp4',exact:true}).click();
  await page.locator('#lecture-progress').waitFor();await page.getByRole('button',{name:'Clinical Chemistry',exact:true}).click();complete=true;
  await page.waitForFunction(()=>document.querySelector('#notice').textContent.includes('Lecture imported into Clinical Microscopy'),{timeout:15000});
  const data=await page.evaluate(()=>JSON.parse(localStorage.getItem('margin-notebooks-v1')));
  assert.equal(data.notebooks.find(n=>n.name==='Clinical Chemistry').project.lectures.length,0);
  assert.equal(data.notebooks.find(n=>n.name==='Clinical Microscopy').project.lectures[0].text,'Microscopy lecture transcript');
  // Browser migration preserves the single-notebook format used before this update.
  const legacy=await browser.newPage();await legacy.addInitScript(()=>{if(!localStorage.getItem('margin-notebooks-v1'))localStorage.setItem('margin-notebook',JSON.stringify({title:'Old notes',concepts:[{id:'old',title:'Saved concept',text:'Previous notes',source:'old',side:''}],references:[],lectures:[],sources:[],quiz:'',exam:''}))});
  await legacy.goto('http://127.0.0.1:8137');assert.equal(await legacy.locator('#notebook-tabs button').count(),5);assert.equal(await legacy.locator('[aria-label="Class material"]').inputValue(),'Previous notes');
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:'/tmp/margin-notebooks-mobile.png',fullPage:true});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  assert.deepEqual(errors,[]);console.log('Browser checks passed: category import, subject isolation, asynchronous destinations, persistence, migration, mobile layout.');
 }finally{if(browser)await browser.close();server.kill()}
})().catch(e=>{console.error(e);process.exitCode=1});
