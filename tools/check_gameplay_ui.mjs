import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {fileURLToPath} from 'node:url';
import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
// Run: node tools/check_gameplay_ui.mjs [--screenshots] [--puzzles-only]
// Uses an isolated save and offline model. No remote AI or dependency installation.
// GAMEPLAY_QA_GAME_ROOT selects an extracted portable game for the same checks.
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const gameRoot = path.resolve(process.env.GAMEPLAY_QA_GAME_ROOT || root);
const out = path.join(root, '.local', 'gameplay-ui-qa', String(Date.now()));
fs.mkdirSync(out, {recursive: true});
const chromeProfile = fs.mkdtempSync(path.join(out, 'chrome-'));
function websocketClass() {
 if (globalThis.WebSocket) return globalThis.WebSocket;
 const require=createRequire(import.meta.url);
 try { return require('ws'); } catch {}
 const cache=path.join(process.env.LOCALAPPDATA||os.homedir(),'npm-cache','_npx');
 for(const folder of fs.existsSync(cache)?fs.readdirSync(cache):[]){try{return require(path.join(cache,folder,'node_modules','ws'));}catch{}}
 throw new Error('Use Node 22+ or an existing ws package.');
}
function chromeExecutable() {
 if(process.env.DIALOGUE_QA_CHROME)return process.env.DIALOGUE_QA_CHROME;
 const cache=path.join(process.env.LOCALAPPDATA||os.homedir(),'ms-playwright');
 const folders=fs.existsSync(cache)?fs.readdirSync(cache).filter(p=>/^chromium-\d+$/.test(p)).sort((a,b)=>Number(b.split('-')[1])-Number(a.split('-')[1])):[];
 const candidates=folders.map(p=>path.join(cache,p,'chrome-win64','chrome.exe'));
 candidates.push(path.join(process.env.PROGRAMFILES||'C:/Program Files','Google/Chrome/Application/chrome.exe'));
 const found=candidates.find(p=>fs.existsSync(p));
 if(!found)throw new Error('Chrome not found. Set DIALOGUE_QA_CHROME.');return found;
}
async function stopChild(child) {
 if(!child||child.exitCode!==null)return;
 await new Promise(resolve=>{const timer=setTimeout(resolve,5000);child.once('exit',()=>{clearTimeout(timer);resolve();});child.kill();});
}
const checks=[],errors=[],networkErrors=[];let server,browser,socket,captureFailure;
try {
 server=spawn(process.env.GAMEPLAY_QA_PYTHON||process.env.DIALOGUE_QA_PYTHON||path.join(gameRoot,'runtime/python.exe'),['-B','-X','utf8',path.join(root,'tools/gameplay_ui_server.py')],{cwd:gameRoot,windowsHide:true,stdio:['ignore','pipe','pipe'],env:{...process.env,PYTHONIOENCODING:'utf-8'}});
 const port=await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(new Error('Server startup timeout')),15000);server.stdout.on('data',data=>{const m=data.toString().match(/QA_PORT=(\d+)/);if(m){clearTimeout(timer);resolve(Number(m[1]));}});server.once('error',reject);server.once('exit',code=>reject(new Error('Server exited '+code)));});
 const base='http://127.0.0.1:'+port;
 browser=spawn(chromeExecutable(),['--headless=new','--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-component-update','--disable-extensions','--disable-breakpad','--autoplay-policy=document-user-activation-required','--remote-debugging-port=0','--user-data-dir='+chromeProfile,'about:blank'],{windowsHide:true,stdio:['ignore','ignore','pipe']});
 const ws=await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(new Error('Chrome startup timeout')),15000);browser.stderr.on('data',data=>{const m=data.toString().match(/DevTools listening on (ws:\/\/\S+)/);if(m){clearTimeout(timer);resolve(m[1]);}});browser.once('error',reject);});
 const Socket=websocketClass();socket=new Socket(ws);await new Promise((resolve,reject)=>{socket.addEventListener('open',resolve,{once:true});socket.addEventListener('error',reject,{once:true});});
 let id=0;const pending=new Map();
 socket.addEventListener('message',event=>{const m=JSON.parse(typeof event.data==='string'?event.data:event.data.toString());if(m.method==='Network.responseReceived'&&m.params.response.status>=400&&/\/(assets|api)\//.test(m.params.response.url))networkErrors.push({url:m.params.response.url,status:m.params.response.status});if(m.id&&pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);clearTimeout(p.timer);m.error?p.reject(new Error(JSON.stringify(m.error))):p.resolve(m.result);}if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails.exception?.description||m.params.exceptionDetails.text);});
 const cdp=(method,params={},sessionId)=>new Promise((resolve,reject)=>{const n=++id,timer=setTimeout(()=>reject(new Error('CDP timeout '+method)),20000);pending.set(n,{resolve,reject,timer});socket.send(JSON.stringify({id:n,method,params,...(sessionId?{sessionId}:{})}));});
 const {targetId}=await cdp('Target.createTarget',{url:'about:blank'}),{sessionId}=await cdp('Target.attachToTarget',{targetId,flatten:true});
 const call=(method,params={})=>cdp(method,params,sessionId);
 await call('Runtime.enable');await call('Page.enable');await call('Network.enable');
 const evaluate=async expression=>{const r=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw new Error(r.exceptionDetails.exception?.description||r.exceptionDetails.text);return r.result.value;};
 captureFailure=async()=>{const r=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});fs.writeFileSync(path.join(out,'failed.png'),Buffer.from(r.data,'base64'));fs.writeFileSync(path.join(out,'failure-state.json'),JSON.stringify(await evaluate(`(async()=>({game:await fetch('/api/game').then(r=>r.json()).then(d=>d.game),puzzle:document.querySelector('.puzzle-host')?.shadowRoot.innerHTML,overlay:document.querySelector('#overlay')?.outerHTML}))()`),null,2));};
 const wait=async(expression,label=expression)=>{for(let i=0;i<150;i++){if(await evaluate(expression))return;await new Promise(resolve=>setTimeout(resolve,70));}throw new Error('Timeout '+label+' '+JSON.stringify(await evaluate(`({error:document.querySelector('#error-text')?.textContent,images:[...document.images].filter(i=>!i.complete||!i.naturalWidth).map(i=>i.src)})`)));};
 const check=async(label,expression)=>{const value=typeof expression==='string'?await evaluate(expression):expression;checks.push({label,pass:!!value});if(!value)throw new Error('Failed '+label);};
 const viewport=async(width,height=900)=>{await call('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:width===390?2:1,mobile:width<601});await evaluate('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))');};
 const navigate=async url=>{const previous=await evaluate('performance.timeOrigin');await call('Page.navigate',{url:base+url});await wait(`performance.timeOrigin!==${previous}&&document.readyState==='complete'&&!!window.TrainAudio`);await evaluate('document.fonts.ready');};
 const ready=async()=>wait(`document.querySelector('#scene-loading')?.hidden&&document.querySelector('#save-status')?.textContent==='기록 보관됨'`);
 const seed=async phase=>{await navigate('/qa/new?phase='+phase);await ready();};
 const click=async selector=>{
  const p=await evaluate(`(()=>{const el=document.querySelector(${JSON.stringify(selector)});if(!el)throw new Error('Missing '+${JSON.stringify(selector)});el.scrollIntoView({block:'center',inline:'nearest'});const r=el.getBoundingClientRect(),left=Math.max(0,r.left),top=Math.max(0,r.top),right=Math.min(innerWidth,r.right),bottom=Math.min(innerHeight,r.bottom);for(const fy of [.5,.3,.7,.1,.9,.2,.8,.05,.95])for(const fx of [.5,.3,.7,.1,.9,.2,.8,.05,.95]){const x=left+(right-left)*fx,y=top+(bottom-top)*fy;if(right>left&&bottom>top&&el.contains(document.elementFromPoint(x,y)))return{x,y};}throw new Error('Control is covered: '+${JSON.stringify(selector)});})()`);
  await call('Input.dispatchMouseEvent',{type:'mouseMoved',...p});await call('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...p});await call('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...p});
 };
 const snapshot=async name=>{if(!process.argv.includes('--screenshots')&&!name.startsWith('failed'))return;await evaluate('document.fonts.ready.then(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))))');const r=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});fs.writeFileSync(path.join(out,name+'.png'),Buffer.from(r.data,'base64'));};
 const images=async()=>wait(`[...document.querySelector('#overlay').querySelectorAll('img')].every(i=>i.complete&&i.naturalWidth)`);
 const openBag=async()=>{await click('#bag-btn');await wait(`document.querySelector('#overlay').dataset.inventoryMode==='overview'`);await images();};
 const openItem=async id=>{
  const result=await evaluate(`fetch('/api/game').then(r=>r.json())`);
  const target=result.game.inventory.findIndex(i=>i.id===id),capacity=await evaluate(`matchMedia('(max-width:600px)').matches?6:8`);
  if(await evaluate(`document.querySelector('#overlay').dataset.inventoryMode!=='overview'`)){await click('.inventory-back');await ready();}
  while(!await evaluate(`!!document.querySelector('.inventory-card[data-item-id=${JSON.stringify(id)}]')`)){
   const page=await evaluate(`document.querySelector('.inventory-overview .inventory-page-number')?.textContent`);
   await click('.inventory-overview .inventory-pager [aria-label="다음 페이지"]');await images();
   if(page===await evaluate(`document.querySelector('.inventory-overview .inventory-page-number')?.textContent`))throw new Error('Pagination failed '+target+'/'+capacity);
  }
  await click('.inventory-card[data-item-id="'+id+'"]');await ready();await wait(`document.querySelector('#overlay').dataset.inventoryMode==='detail'&&!!document.querySelector('.inventory-record-image')`);await images();
 };
 const fit=async label=>{
  const metrics=await evaluate(`(()=>{const d=document.querySelector('#overlay'),r=d.getBoundingClientRect();return {viewport:[innerWidth,innerHeight],locked:getComputedStyle(document.documentElement).overflow==='hidden',rect:{left:r.left,top:r.top,right:r.right,bottom:r.bottom},elements:[d,...d.querySelectorAll('.inventory-overview,.inventory-detail,.item-list,.book-page')].map(el=>({name:el.className,w:el.clientWidth,sw:el.scrollWidth,h:el.clientHeight,sh:el.scrollHeight}))};})()`);
  const r=metrics.rect,pass=metrics.locked&&r.left>=-1&&r.top>=-1&&r.right<=metrics.viewport[0]+1&&r.bottom<=metrics.viewport[1]+1&&metrics.elements.every(e=>e.sw<=e.w+1&&e.sh<=e.h+1);
  if(!pass){console.error(metrics);await snapshot('failed-fit');}
  await check(label,pass);
 };

 if(!process.argv.includes('--puzzles-only')){
 if(!process.argv.includes('--visuals-only')){
 await viewport(1440);await navigate('/');
 await wait(`Number.isFinite(TrainAudio.element.duration)&&TrainAudio.element.duration>10`);
 await check('MP3 is local and loops',`TrainAudio.element.loop&&TrainAudio.element.currentSrc.endsWith('/assets/audio/train-theme.mp3')`);
 await click('.main');await wait(`!TrainAudio.element.paused`);
 await check('music starts after a real user gesture',`TrainAudio.element.currentTime>=0&&!TrainAudio.element.paused`);
 await evaluate(`TrainAudio.setVolume(35)`);
 await check('real audio volume follows preference',`TrainAudio.element.volume===.35&&JSON.parse(localStorage.getItem('noTerminus.settings')).bgm===35`);
 await click('[data-bgm-toggle]');await check('title sound button mutes music',`TrainAudio.isMuted()&&TrainAudio.element.paused`);
 await click('[data-bgm-toggle]');await wait(`!TrainAudio.element.paused`);
 await evaluate(`TrainAudio.setVolume(0)`);await click('[data-bgm-toggle]');
 await wait(`!TrainAudio.element.paused`);await check('zero volume can be enabled with one click',`TrainAudio.getVolume()>0&&!TrainAudio.isMuted()`);
 await evaluate(`TrainAudio.setVolume(35);TrainAudio.element.currentTime=11`);
 await navigate('/detail');await wait(`Number.isFinite(TrainAudio.element.duration)`);
 await check('boarding page restores the track position and volume',`TrainAudio.getVolume()===35&&TrainAudio.element.currentTime>=10`);
 await seed('base');await click('#bag-btn');await wait(`!TrainAudio.element.paused`);
 await evaluate(`TrainAudio.element.currentTime=TrainAudio.element.duration-.15`);
 await wait(`TrainAudio.element.currentTime<2&&!TrainAudio.element.paused`,'native audio loop crosses end of track');
 await check('track repeats naturally at its end',`TrainAudio.element.loop&&!TrainAudio.element.ended`);
 await evaluate(`TrainAudio.setMuted(true)`);
 }

 for(const [width,height] of [[1440,1000],[1024,768],[768,1024],[390,844],[320,568]]){
  await viewport(width,height);await seed('base');await openBag();await fit('overview fits without internal scrolling '+width);
  await check('overview uses the supplied-style book and taped frame '+width,`getComputedStyle(document.querySelector('.inventory-overview')).backgroundImage.includes('book-overview.png')&&!!document.querySelector('.inventory-mount-art')`);
  await snapshot('overview-'+width);
  for(const id of ['ticket_current','facility_manual','route_report']){
   await openItem(id);await fit(id+' fits without internal scrolling '+width);
   await check(id+' explanation is an actual PNG '+width,`(()=>{const p=document.querySelector('.book-page'),i=p.querySelector('.inventory-record-image');return i.naturalWidth===900&&i.naturalHeight===1120&&i.src.endsWith('.png')&&p.querySelectorAll('p,table,h3').length===0;})()`);
   await snapshot(id+'-'+width);
   if(width<=600&&id==='ticket_current'){
    await click('.inventory-catalog .inventory-pager [aria-label="다음 페이지"]');await images();
    await check('mobile catalog next button is clear of close button '+width,`document.querySelector('#overlay').open&&document.querySelector('.inventory-catalog .inventory-page-number').textContent.startsWith('2 /')`);
    await click('.inventory-catalog .inventory-pager [aria-label="이전 페이지"]');await images();
   }
   await click('.inventory-back');await ready();await images();
  }
  await check('general dialogue uses supplied font '+width,`getComputedStyle(document.querySelector('.dialogue-text')).fontFamily.startsWith('RenaissanceText')`);
  await check('title keeps its previous font '+width,`!getComputedStyle(document.querySelector('.game-brand')).fontFamily.includes('RenaissanceText')`);
 }
 await viewport(1440,1000);await seed('dark');await openBag();await openItem('flashlight');
 await check('flashlight action is a printed dark paper image',`document.querySelector('[aria-label="손전등 사용"] img')?.src.endsWith('/actions/use-flashlight.png')`);
 await snapshot('flashlight-action');await click('[aria-label="손전등 사용"]');await ready();
 await check('using flashlight lights the actual scene and closes book',`!document.querySelector('#overlay').open&&document.querySelector('#darkness').classList.contains('flashlight-mask')`);
 await check('closing inventory restores normal page scrolling',`getComputedStyle(document.documentElement).overflow!=='hidden'`);
 await seed('crew');await openBag();await openItem('route_report');await click('[aria-label="보고서 내용 확인"]');await ready();
 await check('report confirmation still records a completed read',`fetch('/api/game').then(r=>r.json()).then(d=>d.game.inventory.find(i=>i.id==='route_report').read&&!document.querySelector('#overlay').open)`);
 await seed('proof');await openBag();await openItem('ticket_current');await click('[aria-label="이 물건을 최종 증거로 제출"]');await ready();
 await check('evidence button preserves final confirmation',`document.querySelector('#overlay').dataset.view==='confirm'`);
 await check('confirmation buttons also use dark paper images',`document.querySelector('.modal-actions .primary img')?.src.endsWith('/actions/confirm-final.png')`);
 await check('opening submission has not spent final attempt',`fetch('/api/game').then(r=>r.json()).then(d=>d.game.attempts===1&&d.game.status==='playing')`);
 await snapshot('evidence-confirmation');await click('[aria-label="취소하고 다시 살펴보기"]');await ready();
 await check('cancelling keeps final attempt',`fetch('/api/game').then(r=>r.json()).then(d=>d.game.attempts===1&&!d.game.confirmation)`);
 for(const [phase,suffix,contains] of [['early','00',false],['base','10',false],['full','11',true]]){
  await seed(phase);await openBag();await openItem('elder_testimony');
  await check('testimony uses state-specific image '+phase,`document.querySelector('.inventory-record-image').src.endsWith('/elder-testimony-${suffix}.png')&&document.querySelector('.inventory-record-image').alt.includes('삶과 죽음')===${contains}`);
 }
 await seed('returned');await openBag();await openItem('ticket_old');await check('returned ticket uses the preserved-record image',`document.querySelector('.inventory-record-image').src.endsWith('/ticket-old-returned.png')`);
 await click('#close-overlay');await click('#menu-btn');
 await evaluate(`(()=>{const s=document.querySelector('input[aria-label="배경음악 음량"]');s.value='20';s.dispatchEvent(new Event('input',{bubbles:true}));})()`);
 await check('in-game menu changes actual music volume',`TrainAudio.getVolume()===20&&TrainAudio.element.volume===.2`);
 for(const [width,height] of [[1440,1000],[390,844]]){
  await viewport(width,height);await seed('acquire');await click('#choice-list .choice-button');await ready();
  await wait(`!document.querySelector('#acquisition-notice').hidden&&document.querySelector('#acquisition-notice img')?.complete`);
  await check('new acquisition has real taped-frame artwork '+width,`getComputedStyle(document.querySelector('.acquired-icon')).backgroundImage.includes('photo-mount.png')`);
  await check('acquisition notice fits its paper '+width,`(()=>{const el=document.querySelector('#acquisition-notice'),r=el.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth&&el.scrollWidth<=el.clientWidth+1;})()`);
  await snapshot('acquisition-'+width);
 }
 // Exercise actual title/name routes and API, rather than a rendered HTML fixture.
 await viewport(390,844);await navigate('/');await click('#settingsBtn');
 await check('title settings opens',`document.querySelector('#settingsDialog').open`);
 await call('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
 await call('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
 await check('title settings closes with Escape',`!document.querySelector('#settingsDialog').open`);
 await click('.boarding-pass');await wait(`!!document.querySelector('#passengerName')`);
 await check('empty passenger name is blocked',`document.querySelector('#issueBtn').disabled`);
 await evaluate(`document.querySelector('#passengerName').value='123';document.querySelector('#passengerName').dispatchEvent(new Event('input'))`);
 await check('numeric passenger name is blocked',`document.querySelector('#issueBtn').disabled`);
 await evaluate(`document.querySelector('#passengerName').value='윤슬';document.querySelector('#passengerName').dispatchEvent(new Event('input'))`);
 await check('valid passenger name enables issue without horizontal overflow',`!document.querySelector('#issueBtn').disabled&&document.documentElement.scrollWidth<=innerWidth+1`);
 await click('#issueBtn');await ready();
 await check('issued passenger name reaches the real game',`fetch('/api/game').then(r=>r.json()).then(d=>d.game.username==='윤슬'&&d.game.location.id==='car_1'&&d.game.status==='playing')`);
 await click('[data-hotspot="window"]');await wait(`document.querySelector('#overlay').dataset.view==='window'`);
 await wait(`document.querySelector('#overlay video')?.readyState>=2`);
 await check('local window video decodes and loops',`(()=>{const v=document.querySelector('#overlay video');return v.loop&&v.muted&&v.playsInline&&v.videoWidth>0;})()`);
 await click('#close-overlay');
 }
 // Pull the emergency lever through the real service and enter the crew room.
 const shadowClick=async selector=>{
  await wait(`(()=>{const r=document.querySelector('.puzzle-host')?.shadowRoot;return r&&[...r.querySelectorAll('link')].every(l=>!!l.sheet)&&[...r.querySelectorAll('img')].every(i=>i.complete&&i.naturalWidth);})()`,'puzzle stylesheet and artwork');
  await evaluate(`document.fonts.ready.then(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))))`);
  const p=await evaluate(`(()=>{const root=document.querySelector('.puzzle-host').shadowRoot,el=root.querySelector(${JSON.stringify(selector)});el.scrollIntoView({block:'center'});const r=el.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2;if(!el.contains(root.elementFromPoint(x,y)))throw new Error('Puzzle control is covered: '+${JSON.stringify(selector)});return{x,y};})()`);
  await call('Input.dispatchMouseEvent',{type:'mouseMoved',...p});await call('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...p});await call('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...p});
 };
 const puzzle=`document.querySelector('.puzzle-host')?.shadowRoot`;
 for(const [width,height] of [[1440,900],[390,844]]){
  await viewport(width,height);await seed('door');await click('[data-hotspot="inspection_cover"]');
  await wait(`${puzzle}?.querySelector('.cover-button')`);
  await check('door starts locked behind its cover '+width,`${puzzle}.querySelector('.lever').disabled&&${puzzle}.querySelector('.enter-room').hidden`);
  await shadowClick('.cover-button');await ready();
  await check('unread manual preserves the emergency access gate '+width,`${puzzle}.querySelector('.lever').disabled`);
  await shadowClick('.inventory');await wait(`document.querySelector('#overlay').dataset.inventoryMode==='overview'`);await images();
  await openItem('facility_manual');await click('#close-overlay');
  if(!await evaluate(`document.querySelector('#dialogue-box').hidden`))await click('#close-dialogue');
  await click('[data-hotspot="inspection_cover"]');await wait(`${puzzle}?.querySelector('.cover-button')`);
  await shadowClick('.cover-button');await ready();
  await wait(`${puzzle}.querySelector('.lever').disabled===false`);
  await shadowClick('.lever');await ready();
  await check('pulling the lever unlocks entry '+width,`${puzzle}.querySelector('.lever').classList.contains('is-down')&&!${puzzle}.querySelector('.enter-room').hidden`);
  await shadowClick('.enter-room');await ready();
  await check('unlocked door enters the real crew scene '+width,`fetch('/api/game').then(r=>r.json()).then(d=>d.game.location.id==='crew'&&!document.querySelector('#overlay').open)`);
 }
 // Validate real dial mechanics, confirmation cancellation, arrival and both endings.
 for(const [width,height,correct] of [[1440,900,true],[390,844,false]]){
  await viewport(width,height);await seed('control');await click('[data-hotspot="control"]');
  await wait(`${puzzle}?.querySelector('.panel__bg')?.naturalWidth>0`);
  await check('control begins with blank station and zero dials '+width,`${puzzle}.querySelector('.station').value===''&&[...${puzzle}.querySelectorAll('.dial')].every(d=>d.getAttribute('aria-valuenow')==='0')`);
  await shadowClick('.lever');
  await check('blank station cannot spend the last attempt '+width,`fetch('/api/game').then(r=>r.json()).then(d=>d.game.attempts===1&&!d.game.confirmation&&document.querySelector('#overlay').dataset.view==='control')`);
  await evaluate(`(()=>{const d=${puzzle}.querySelector('.dial');d.click();d.dispatchEvent(new WheelEvent('wheel',{deltaY:1,cancelable:true}));})()`);
  await check('dial click and wheel rotate separately '+width,`${puzzle}.querySelector('.dial').getAttribute('aria-valuenow')==='2'`);
  await evaluate(`(()=>{const r=${puzzle};r.querySelector('.station').value='아지산역';r.querySelector('.station').dispatchEvent(new Event('input'));[...r.querySelectorAll('.dial')].forEach((d,i)=>d.dispatchEvent(new KeyboardEvent('keydown',{key:'2026'[i],bubbles:true})));})()`);
  await shadowClick('.lever');await ready();await wait(`document.querySelector('#overlay').dataset.view==='confirm'`);
  await check('prepared control still preserves its last attempt '+width,`fetch('/api/game').then(r=>r.json()).then(d=>d.game.attempts===1&&d.game.confirmation.password==='2026'&&d.game.confirmation.destination==='아지산역')`);
  await click('[aria-label="취소하고 다시 살펴보기"]');await ready();
  await check('cancel restores station and all dial values '+width,`${puzzle}.querySelector('.station').value==='아지산역'&&[...${puzzle}.querySelectorAll('.dial')].map(d=>d.getAttribute('aria-valuenow')).join('')==='2026'`);
  if(!correct)await evaluate(`${puzzle}.querySelectorAll('.dial')[3].dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowDown',bubbles:true}))`);
  await shadowClick('.lever');await ready();await wait(`document.querySelector('#overlay').dataset.view==='confirm'`);
  await click('[aria-label="최종 확정"]');await ready();
  if(correct){
   await check('correct control arrives before disembarkation',`fetch('/api/game').then(r=>r.json()).then(d=>d.game.attempts===0&&d.game.status==='playing'&&d.game.location.id==='platform')`);
   await check('arrival enables the map exit even when it is the current location',`!document.querySelector('#train-map [data-location="platform"]').disabled`);
   await click('#train-map [data-location="platform"]');await ready();await wait(`document.querySelector('#overlay').dataset.view==='ending'`);
   await check('explicit disembarkation opens good ending and disables chat',`fetch('/api/game').then(r=>r.json()).then(d=>d.game.status==='good'&&document.querySelector('#send-btn').disabled&&!!document.querySelector('.ending-paper'))`);
  }else{
   await wait(`document.querySelector('#overlay').dataset.view==='ending'`);
   await check('wrong final control spends exactly one attempt and opens bad ending',`fetch('/api/game').then(r=>r.json()).then(d=>d.game.attempts===0&&d.game.status==='bad'&&d.game.reason==='wrong_control'&&document.querySelector('#send-btn').disabled)`);
  }
 }
 await check('no failed game or asset responses',networkErrors.length===0);
 await check('no browser exceptions',errors.length===0);
 console.log(JSON.stringify({passed:checks.length,gameRoot,artifacts:out},null,2));
}catch(error){errors.push(String(error.stack||error));console.error(error.stack||error);await captureFailure?.().catch(()=>{});process.exitCode=1;}
finally{
 fs.writeFileSync(path.join(out,'result.json'),JSON.stringify({gameRoot,checks,errors,networkErrors},null,2));
 socket?.close();await stopChild(browser);await stopChild(server);
 const resolvedOut=fs.realpathSync(out),resolvedProfile=fs.realpathSync(chromeProfile);
 if(resolvedProfile.startsWith(resolvedOut+path.sep)&&path.basename(resolvedProfile).startsWith('chrome-'))fs.rmSync(resolvedProfile,{recursive:true,force:true,maxRetries:8,retryDelay:150});
}

