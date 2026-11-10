'use strict';
(async()=>{
const frame=document.querySelector('iframe'),results=document.getElementById('results');
const pause=ms=>new Promise(r=>setTimeout(r,ms));
async function wait(check,label){for(let i=0;i<100;i++){if(await check())return;await pause(100);}throw Error('Timed out: '+label);}
function pass(text){const li=document.createElement('li');li.textContent='PASS · '+text;results.append(li);}
let win,doc;
async function read(){return new Promise((resolve,reject)=>{const r=win.indexedDB.open('meddesk-benchmark-test',1);r.onsuccess=()=>{const db=r.result;const tx=db.transaction('workspace');const q=tx.objectStore('workspace').get('project');q.onsuccess=()=>{resolve(q.result);db.close();};q.onerror=()=>reject(q.error);};r.onerror=()=>reject(r.error);});}
async function hash(blob){const bytes=await blob.arrayBuffer();return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))).map(x=>x.toString(16).padStart(2,'0')).join('');}
try{
await wait(()=>frame.contentWindow?.document.getElementById('people')?.children.length>0,'app initialization');win=frame.contentWindow;doc=frame.contentDocument;
await wait(async()=>(await read())?.seeded,'reference audio');pass('Application initializes in isolated IndexedDB');
const name='QA Participant '+Date.now();doc.getElementById('add-person').click();doc.getElementById('new-name').value=name;doc.getElementById('name-dialog').close('save');
await wait(async()=>(await read()).people.some(p=>p.name===name),'participant save');pass('New participant saves without code changes');
doc.getElementById('role').value='Dr. QA';doc.getElementById('role').dispatchEvent(new win.Event('change'));
doc.getElementById('add-script').click();doc.getElementById('new-name').value='QA reading';doc.getElementById('name-dialog').close('save');
await wait(()=>doc.getElementById('script-title').value==='QA reading','new script');doc.getElementById('script-text').value='This is a synthetic audio test.';doc.getElementById('script-text').dispatchEvent(new win.Event('input'));
await wait(async()=>(await read()).scripts.some(s=>s.text==='This is a synthetic audio test.'),'script save');pass('New script and editable role persist');
const bytes=new ArrayBuffer(44+16000),view=new DataView(bytes);function text(offset,s){for(let i=0;i<s.length;i++)view.setUint8(offset+i,s.charCodeAt(i));}text(0,'RIFF');view.setUint32(4,bytes.byteLength-8,true);text(8,'WAVEfmt ');view.setUint32(16,16,true);view.setUint16(20,1,true);view.setUint16(22,1,true);view.setUint32(24,8000,true);view.setUint32(28,16000,true);view.setUint16(32,2,true);view.setUint16(34,16,true);text(36,'data');view.setUint32(40,16000,true);
doc.getElementById('consent').checked=true;const transfer=new win.DataTransfer();transfer.items.add(new win.File([bytes],'qa-silence.wav',{type:'audio/wav'}));doc.getElementById('upload').files=transfer.files;doc.getElementById('upload').dispatchEvent(new win.Event('change'));
await wait(async()=>(await read()).takes.some(t=>t.filename==='qa-silence.wav'),'upload');let stored=await read();const take=stored.takes.find(t=>t.filename==='qa-silence.wav');if(take.role!=='Dr. QA'||take.scriptText!=='This is a synthetic audio test.')throw Error('Wrong take mapping');pass('Upload assigns the correct participant, role and script snapshot');
await wait(()=>doc.querySelector('.take audio')?.readyState>=1,'WAV metadata');if(Math.abs(doc.querySelector('.take audio').duration-1)>.1)throw Error('Wrong WAV duration');pass('Browser decodes uploaded WAV with correct duration');
const row=doc.querySelector('.take');row.querySelector('input').value='QA review note';row.querySelector('input').dispatchEvent(new win.Event('change'));row.querySelector('.actions button').click();
await wait(async()=>{const t=(await read()).takes.find(t=>t.id===take.id);return t.accepted&&t.notes==='QA review note';},'review save');pass('Review notes and acceptance persist');
let exported;const originalURL=win.URL.createObjectURL.bind(win.URL),originalClick=win.HTMLAnchorElement.prototype.click;win.URL.createObjectURL=blob=>{if(blob.type==='application/json')exported=blob;return originalURL(blob);};win.HTMLAnchorElement.prototype.click=function(){};
await win.exportProject();win.URL.createObjectURL=originalURL;win.HTMLAnchorElement.prototype.click=originalClick;if(!exported)throw Error('Export not produced');const exportedText=await exported.text();const parsed=JSON.parse(exportedText);win.validateProject(parsed);pass('Actual export produces a valid project with embedded audio');
const before=await read(),hashes=await Promise.all(before.takes.map(t=>hash(t.blob)));win.confirm=()=>true;await win.importProject(new win.File([exportedText],'qa-backup.json',{type:'application/json'}));const after=await read();if(after.people.length!==before.people.length||after.scripts.length!==before.scripts.length||after.takes.length!==before.takes.length)throw Error('Restored counts differ');for(let i=0;i<after.takes.length;i++){if(await hash(after.takes[i].blob)!==hashes[i])throw Error('Restored audio differs');}pass('Actual browser import restores every audio byte and project counts');
const count=after.takes.length;await win.importProject(new win.File(['{"version":999}'],'invalid.json'));if((await read()).takes.length!==count)throw Error('Invalid import changed data');pass('Invalid project rejected without overwriting saved data');
frame.contentWindow.location.reload();await pause(300);await wait(()=>frame.contentDocument.getElementById('people')?.children.length===after.people.length,'reload roster');win=frame.contentWindow;doc=frame.contentDocument;const reloaded=await read();const restored=reloaded.takes.find(t=>t.id===take.id);if(!restored?.accepted||restored.notes!=='QA review note')throw Error('Review lost on reload');pass('Reload retains participants, scripts, audio and review status');
document.getElementById('status').textContent='ALL 10 CHECKS PASSED';
}catch(e){document.getElementById('status').textContent='FAILED · '+e.message;document.getElementById('status').className='fail';console.error(e);}
})();
