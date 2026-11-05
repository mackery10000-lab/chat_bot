import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {fileURLToPath} from 'node:url';
import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {createHash} from 'node:crypto';
// Run: node tools/check_gameplay_ui.mjs [--screenshots] [--puzzles-only|--cinematics-only|--doors-only|--inventory-only]
// Uses an isolated save and offline model. No remote AI or dependency installation.
// GAMEPLAY_QA_GAME_ROOT selects an extracted portable game for the same checks.
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const gameRoot = path.resolve(process.env.GAMEPLAY_QA_GAME_ROOT || root);
const cinematicsOnly = process.argv.includes('--cinematics-only');
const doorsOnly = process.argv.includes('--doors-only');
const inventoryOnly = process.argv.includes('--inventory-only');
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
const checks=[],errors=[],networkErrors=[],inventoryMetrics=[];let server,browser,socket,captureFailure,serverLog='';
try {
 server=spawn(process.env.GAMEPLAY_QA_PYTHON||process.env.DIALOGUE_QA_PYTHON||path.join(gameRoot,'runtime/python.exe'),['-B','-X','utf8',path.join(root,'tools/gameplay_ui_server.py')],{cwd:gameRoot,windowsHide:true,stdio:['ignore','pipe','pipe'],env:{...process.env,PYTHONIOENCODING:'utf-8'}});
 // Flask logs every request. Drain the pipe so long suites cannot block the
 // server when its OS stderr buffer fills, retaining only useful diagnostics.
 server.stderr.on('data',data=>{serverLog=(serverLog+data.toString()).slice(-8000);});
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
 captureFailure=async()=>{const r=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});fs.writeFileSync(path.join(out,'failed.png'),Buffer.from(r.data,'base64'));fs.writeFileSync(path.join(out,'failure-state.json'),JSON.stringify(await evaluate(`(async()=>({game:await fetch('/api/game').then(r=>r.json()).then(d=>d.game),puzzle:document.querySelector('.puzzle-host')?.shadowRoot.innerHTML,overlay:document.querySelector('#overlay')?.outerHTML,cinematic:document.querySelector('#cinematic')?.outerHTML,video:(()=>{const v=document.querySelector('#cinematic-video');return v?{src:v.currentSrc,readyState:v.readyState,error:v.error?.code,paused:v.paused,time:v.currentTime,duration:v.duration}:null;})()}))()`),null,2));};
 const wait=async(expression,label=expression,timeoutMs=10500)=>{const deadline=Date.now()+timeoutMs;while(Date.now()<deadline){if(await evaluate(expression))return;await new Promise(resolve=>setTimeout(resolve,70));}throw new Error('Timeout '+label+' '+JSON.stringify(await evaluate(`({error:document.querySelector('#error-text')?.textContent,images:[...document.images].filter(i=>!i.complete||!i.naturalWidth).map(i=>i.src)})`)));};
 const check=async(label,expression)=>{const value=typeof expression==='string'?await evaluate(expression):expression;checks.push({label,pass:!!value});if(!value)throw new Error('Failed '+label);};
 const viewport=async(width,height=900)=>{await call('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:width===390?2:1,mobile:width<601});await evaluate('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))');};
 const navigate=async url=>{const previous=await evaluate('performance.timeOrigin');await call('Page.navigate',{url:base+url});await wait(`performance.timeOrigin!==${previous}&&document.readyState==='complete'&&!!window.TrainAudio`);await evaluate('document.fonts.ready');};
 const ready=async()=>wait(`document.querySelector('#scene-loading')?.hidden&&document.querySelector('#save-status')?.textContent==='기록 보관됨'`);
 const seed=async phase=>{await navigate('/qa/new?phase='+phase);await ready();};
 const click=async(selector,hoverOnly=false)=>{
  const p=await evaluate(`(()=>{const el=document.querySelector(${JSON.stringify(selector)});if(!el)throw new Error('Missing '+${JSON.stringify(selector)});el.scrollIntoView({block:'center',inline:'nearest'});const r=el.getBoundingClientRect(),left=Math.max(0,r.left),top=Math.max(0,r.top),right=Math.min(innerWidth,r.right),bottom=Math.min(innerHeight,r.bottom),polygon=el.style.clipPath.match(/[0-9.]+%/g)?.map(parseFloat);if(polygon?.length>=6){const count=polygon.length/2,x=r.left+r.width*polygon.filter((_,i)=>i%2===0).reduce((a,b)=>a+b,0)/count/100,y=r.top+r.height*polygon.filter((_,i)=>i%2===1).reduce((a,b)=>a+b,0)/count/100;if(el.contains(document.elementFromPoint(x,y)))return{x,y};}for(const fy of [.5,.3,.7,.1,.9,.2,.8,.05,.95])for(const fx of [.5,.3,.7,.1,.9,.2,.8,.05,.95]){const x=left+(right-left)*fx,y=top+(bottom-top)*fy;if(right>left&&bottom>top&&el.contains(document.elementFromPoint(x,y)))return{x,y};}throw new Error('Control is covered: '+${JSON.stringify(selector)});})()`);
  await call('Input.dispatchMouseEvent',{type:'mouseMoved',...p});if(hoverOnly)return;await call('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...p});await call('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...p});
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
   const direction=Math.floor(target/capacity)<parseInt(page,10)-1?'이전 페이지':'다음 페이지';
   await click('.inventory-overview .inventory-pager [aria-label="'+direction+'"]');await images();
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
 const captureInventoryRecord=async(label,layout,artwork,actionCount,reference,objectArtwork)=>{
  await fit(label+' fits without scrolling');
  const metrics=await evaluate(`(()=>{
   const page=document.querySelector('.book-page'),image=page.querySelector('.inventory-record-image'),spread=document.querySelector('.inventory-spread'),object=document.querySelector('.inventory-object'),actions=page.querySelector('.document-actions');
   const rect=el=>{const r=el.getBoundingClientRect();return {left:r.left,top:r.top,right:r.right,bottom:r.bottom,width:r.width,height:r.height};};
   const box=rect(image),paper=rect(page),book=rect(spread),leftObject=rect(object),scale=Math.min(box.width/image.naturalWidth,box.height/image.naturalHeight),paintWidth=image.naturalWidth*scale,paintHeight=image.naturalHeight*scale;
   const position=getComputedStyle(image).objectPosition.split(' '),fraction=value=>value==='center'?.5:value==='right'||value==='bottom'?1:parseFloat(value)/100||0;
   const painted={left:box.left+(box.width-paintWidth)*fraction(position[0]),top:box.top+(box.height-paintHeight)*fraction(position[1]),width:paintWidth,height:paintHeight};
   const canvas=document.createElement('canvas');canvas.width=image.naturalWidth;canvas.height=image.naturalHeight;const context=canvas.getContext('2d',{willReadFrequently:true});context.drawImage(image,0,0);const pixels=context.getImageData(0,0,canvas.width,canvas.height).data;
   const ink={left:canvas.width,top:canvas.height,right:-1,bottom:-1,pixels:0};
   for(let y=0;y<canvas.height;y++)for(let x=0;x<canvas.width;x++)if(pixels[(y*canvas.width+x)*4+3]>24){ink.left=Math.min(ink.left,x);ink.top=Math.min(ink.top,y);ink.right=Math.max(ink.right,x);ink.bottom=Math.max(ink.bottom,y);ink.pixels++;}
   return {src:image.currentSrc,alt:image.alt,naturalWidth:image.naturalWidth,naturalHeight:image.naturalHeight,paper,painted,ink,inkScreen:{left:painted.left+ink.left*scale,top:painted.top+ink.top*scale,right:painted.left+(ink.right+1)*scale,bottom:painted.top+(ink.bottom+1)*scale},actionCount:Number(page.dataset.actionCount),actions:actions?rect(actions):null,buttons:actions?[...actions.children].map(rect):[],background:getComputedStyle(spread).backgroundImage,objectSrc:object.querySelector('img').getAttribute('src'),objectFractions:{left:(leftObject.left-book.left)/book.width,top:(leftObject.top-book.top)/book.height,width:leftObject.width/book.width,height:leftObject.height/book.height},onlyRecord:document.querySelectorAll('img[src*="/inventory/records/"]').length===1,bitmapOnly:page.querySelectorAll('p,table,h3').length===0};
  })()`);
  inventoryMetrics.push({label,...metrics});
  await check(label+' uses its own transparent PNG record',metrics.src.endsWith('/records/'+artwork+'.png')&&metrics.naturalWidth===900&&metrics.naturalHeight===1120&&metrics.bitmapOnly&&metrics.onlyRecord);
  await check(label+' preserves the expected action count',metrics.actionCount===actionCount&&metrics.buttons.length===actionCount);
  const p=metrics.paper,i=metrics.inkScreen;
  await check(label+' keeps compact printed content inside the page',metrics.ink.pixels>0&&metrics.ink.left>0&&metrics.ink.top>0&&metrics.ink.right<899&&metrics.ink.bottom<=730&&i.left>=p.left-1&&i.top>=p.top-1&&i.right<=p.right+1&&i.bottom<=p.bottom+1);
  await check(label+' keeps all ink above its action buttons',!metrics.actions||i.bottom<=metrics.actions.top-1);
  await check(label+' keeps action buttons inside their page',metrics.buttons.every(b=>b.width>0&&b.height>=23&&b.left>=p.left-1&&b.top>=p.top-1&&b.right<=p.right+1&&b.bottom<=p.bottom+1));
  const fractions=layout==='mobile'?[.07,.04,.24,.17]:[.05,.10,.39,.80],actual=metrics.objectFractions;
  await check(label+' preserves the book background and left object layout',metrics.background.includes(layout==='mobile'?'record-paper.png':'book-detail.png')&&metrics.objectSrc.endsWith('/inventory/'+objectArtwork+'.png')&&[actual.left,actual.top,actual.width,actual.height].every((value,index)=>Math.abs(value-fractions[index])<.003));
  if(reference){
   const a=metrics.painted,b=reference.painted;
   await check(label+' keeps the same text scale and alignment across action counts',Math.abs(a.width-b.width)<.5&&Math.abs(a.height-b.height)<.5&&Math.abs((a.left-p.left)-(b.left-reference.paper.left))<.5&&Math.abs((a.top-p.top)-(b.top-reference.paper.top))<.5);
  }
  await snapshot('inventory-'+label);
  return metrics;
 };
 const inventoryChecks=async()=>{
  const baselineArg=process.argv.find(arg=>arg.startsWith('--inventory-baseline='));
  if(baselineArg){
   const baselinePath=path.resolve(root,baselineArg.slice('--inventory-baseline='.length)),baseline=JSON.parse(fs.readFileSync(baselinePath,'utf8').replace(/^\uFEFF/,''));
   const changed=baseline.filter(entry=>createHash('sha256').update(fs.readFileSync(path.join(gameRoot,entry.path))).digest('hex')!==entry.sha256).map(entry=>entry.path);
   await check('all '+baseline.length+' original book, object and control PNGs remain byte-identical',changed.length===0);
   if(changed.length)throw new Error('Changed preserved inventory assets: '+changed.join(', '));
  }
  const manifest=JSON.parse(fs.readFileSync(path.join(gameRoot,'public/assets/images/inventory/records/layout-manifest.json'),'utf8').replace(/^\uFEFF/,''));
  await check('record artwork uses the antique font on the shared transparent canvas',manifest.font==='Nanum Myeongjo ExtraBold'&&manifest.canvas[0]===900&&manifest.canvas[1]===1120&&manifest.contentBottom<=730&&Object.keys(manifest.records).length>=12);
  await check('all printed titles share a consistent left edge and top baseline',Object.values(manifest.records).every(record=>record.lines[0]?.x===42&&record.lines[0]?.y===28&&record.inkBounds[3]<=730));
  for(const [suffix,appearance,destination] of [['00',false,false],['10',true,false],['01',false,true],['11',true,true]]){
   const text=manifest.records['elder-testimony-'+suffix+'.png'].lines.map(line=>line.text).join(' ').replace(/\s+/g,'');
   await check('printed testimony '+suffix+' contains only its earned clues',text.includes('누렇게')===appearance&&text.includes('커피')===appearance&&text.includes('삶과죽음')===destination&&!text.includes('아지산'));
  }
  const baseRecords=[['ticket_current','ticket-current',0],['newspaper','newspaper',0],['flashlight','flashlight',1],['facility_manual','facility-manual',0],['ticket_old','ticket-old',1],['route_report','route-report',1],['elder_testimony','elder-testimony-10',0]];
  for(const [width,height] of [[1440,1000],[1024,768],[390,844],[320,568]]){
   await viewport(width,height);await seed('base');await openBag();await fit('inventory overview '+width);
   await check('inventory overview preserves its original book, mounts and close control '+width,`getComputedStyle(document.querySelector('.inventory-overview')).backgroundImage.includes('book-overview.png')&&document.querySelector('.inventory-mount-art')?.getAttribute('src').endsWith('/inventory/photo-mount.png')&&!!document.querySelector('#close-overlay')`);
   await snapshot('inventory-overview-'+width);
   let reference=null;
   const capture=async(id,artwork,actions,label=artwork)=>{
    await openItem(id);
    const metrics=await captureInventoryRecord(label+'-'+width,width<=600?'mobile':'desktop',artwork,actions,reference,id.replaceAll('_','-'));
    reference??=metrics;return metrics;
   };
   for(const [id,artwork,actions] of baseRecords){
    const metrics=await capture(id,artwork,actions);
    if(id==='elder_testimony')await check('testimony appearance state hides the unearned destination clue '+width,metrics.alt.includes('누렇게')&&!metrics.alt.includes('삶과 죽음')&&!metrics.alt.includes('아지산'));
   }
   for(const [phase,id,artwork,actions] of [['returned','ticket_old','ticket-old-returned',1],['early','elder_testimony','elder-testimony-00',0],['hint_only','elder_testimony','elder-testimony-01',0],['full','elder_testimony','elder-testimony-11',0],['proof','ticket_current','ticket-current',1],['proof','flashlight','flashlight',2],['record_two_actions','route_report','route-report',2]]){
    await seed(phase);await openBag();const metrics=await capture(id,artwork,actions,artwork+'-'+phase);
    if(id==='elder_testimony')await check('testimony reveals only earned clues '+phase+' '+width,metrics.alt.includes('누렇게')===(phase==='full')&&metrics.alt.includes('삶과 죽음')===(phase!=='early')&&!metrics.alt.includes('아지산'));
    if(phase==='returned')await check('returned ticket retains its preserved-record explanation '+width,metrics.alt.includes('원본은 노인에게 돌려드렸다'));
   }
  }
 };
 const cinematicReady=async(kind,file)=>{
  await wait(`document.querySelector('#cinematic')?.open&&document.querySelector('#cinematic').dataset.kind===${JSON.stringify(kind)}`);
  await wait(`document.querySelector('#cinematic-video')?.readyState>=2`,'cinematic decodes '+kind);
  await evaluate(`window.__qaVideoEnded=false;document.querySelector('#cinematic-video').addEventListener('ended',()=>window.__qaVideoEnded=true,{once:true})`);
  await check('local '+kind+' video decodes',`(()=>{const v=document.querySelector('#cinematic-video');return v.currentSrc.endsWith('/assets/videos/${file}')&&v.videoWidth>0&&v.videoHeight>0&&Number.isFinite(v.duration)&&v.duration>10&&!v.loop&&v.playsInline;})()`);
  await wait(`!document.querySelector('#cinematic-video').paused&&document.querySelector('#cinematic-video').currentTime>.05`,'cinematic playback starts '+kind);
  await check(kind+' has no playback controls or visible interface',`(()=>{const d=document.querySelector('#cinematic'),v=document.querySelector('#cinematic-video');return !v.controls&&!v.hasAttribute('controls')&&v.disablePictureInPicture&&v.disableRemotePlayback&&[...d.querySelectorAll('button,input,[role="status"],.cinematic-controls')].every(el=>{const r=el.getBoundingClientRect();return r.width<=1||r.height<=1||getComputedStyle(el).visibility==='hidden';});})()`);
  if(await evaluate(`document.querySelector('#cinematic-video').muted`))await click('#cinematic');
  await wait(`!document.querySelector('#cinematic-video').muted`,'first gesture restores cinematic sound '+kind);
  await evaluate(`TrainAudio.setMuted(false);TrainAudio.setVolume(35)`);
  await check(kind+' pauses music and blocks background controls',`TrainAudio.element.paused&&document.querySelector('#cinematic').matches(':modal')`);
  await check(kind+' video fits the viewport',`(()=>{const r=document.querySelector('#cinematic-video').getBoundingClientRect();return r.width>0&&r.height>0&&r.left>=-1&&r.top>=-1&&r.right<=innerWidth+1&&r.bottom<=innerHeight+1;})()`);
  const before=await evaluate(`({time:document.querySelector('#cinematic-video').currentTime,at:performance.now()})`);
  await click('#cinematic');
  for(const [key,code,windowsVirtualKeyCode] of [[' ','Space',32],['k','KeyK',75],['ArrowRight','ArrowRight',39],['ArrowLeft','ArrowLeft',37],['Home','Home',36],['End','End',35],['Escape','Escape',27],['Tab','Tab',9],['MediaPlayPause','MediaPlayPause',179]]){
   await call('Input.dispatchKeyEvent',{type:'keyDown',key,code,windowsVirtualKeyCode});
   await call('Input.dispatchKeyEvent',{type:'keyUp',key,code,windowsVirtualKeyCode});
  }
  await check(kind+' ignores pointer, playback keys and Escape',`(()=>{const v=document.querySelector('#cinematic-video'),elapsed=(performance.now()-${before.at})/1000;return document.querySelector('#cinematic').open&&!v.paused&&!v.ended&&v.playbackRate===1&&v.currentTime>=${before.time}-.2&&v.currentTime<=${before.time}+elapsed+1;})()`);
  await check(kind+' suppresses the video context menu',`(()=>{const e=new MouseEvent('contextmenu',{bubbles:true,cancelable:true});document.querySelector('#cinematic-video').dispatchEvent(e);return e.defaultPrevented;})()`);
  const guardStart=await evaluate(`({time:document.querySelector('#cinematic-video').currentTime,at:performance.now()})`);
  await evaluate(`(()=>{const v=document.querySelector('#cinematic-video');v.pause();v.playbackRate=2;v.currentTime=Math.min(v.duration-1,v.currentTime+5);})()`);
  await wait(`(()=>{const v=document.querySelector('#cinematic-video'),elapsed=(performance.now()-${guardStart.at})/1000;return !v.paused&&!v.seeking&&v.playbackRate===1&&v.currentTime<${guardStart.time}+elapsed+1;})()`,'cinematic rejects pause, seek and rate changes '+kind);
  await check(kind+' restores protected continuous playback',`document.querySelector('#cinematic').dataset.phase==='playing'&&!document.querySelector('#cinematic-video').ended`);
  if(process.argv.includes('--screenshots'))await wait(`document.querySelector('#cinematic-video').currentTime>=3`,'cinematic preview frame '+kind);
  await snapshot('cinematic-'+kind+'-'+await evaluate('innerWidth'));
 };
 const finishVideo=async()=>{
  const remaining=await evaluate(`Math.max(0,document.querySelector('#cinematic-video').duration-document.querySelector('#cinematic-video').currentTime)`);
  await wait(`window.__qaVideoEnded`,'video reaches its natural ended event',Math.ceil(remaining*1000)+15000);
 };
 const openingChecks=async()=>{
  await cinematicReady('opening','opening.mp4');
  await check('opening plays before the first game action',`fetch('/api/game').then(r=>r.json()).then(d=>d.game.revision===0&&d.game.location.id==='car_1'&&d.game.status==='playing'&&d.game.attempts===null&&!d.game.clock_running)`);
  await check('opening exposes no skip control',`!document.querySelector('#cinematic-skip')`);
  await finishVideo();await wait(`!document.querySelector('#cinematic').open`);await ready();
  await check('opening completion begins in car 1 without starting the clock',`fetch('/api/game').then(r=>r.json()).then(d=>d.game.location.id==='car_1'&&d.game.status==='playing'&&d.game.attempts===null&&!d.game.clock_running&&d.game.revision===0)`);
  await navigate('/chat');await ready();
  await check('refresh does not replay a completed opening',`!document.querySelector('#cinematic').open`);
 };
 const issueName=async name=>{
  await navigate('/detail');
  await evaluate(`document.querySelector('#passengerName').value=${JSON.stringify(name)};document.querySelector('#passengerName').dispatchEvent(new Event('input'))`);
  await click('#issueBtn');
 };
 const openingRecoveryChecks=async()=>{
  await evaluate(`sessionStorage.removeItem('train.opening.seen')`);
  const {identifier}=await call('Page.addScriptToEvaluateOnNewDocument',{source:`(()=>{
   if(location.pathname!=='/chat')return;
   const originalFetch=window.fetch;
   let failSnapshot=true,blockAutoplay=true;
   window.fetch=function(input,...args){
    const url=new URL(typeof input==='string'?input:input.url,location.href);
    if(failSnapshot&&url.pathname==='/api/game'){failSnapshot=false;return Promise.reject(new TypeError('Offline QA snapshot failure'));}
    return originalFetch.call(this,input,...args);
   };
   const originalPlay=HTMLMediaElement.prototype.play;
   HTMLMediaElement.prototype.play=function(...args){
    if(blockAutoplay&&this.id==='cinematic-video'){blockAutoplay=false;window.__qaAutoplayBlocked=true;return Promise.reject(new DOMException('Offline QA autoplay policy','NotAllowedError'));}
    return originalPlay.apply(this,args);
   };
  })();`});
  await navigate('/chat');
  await call('Page.removeScriptToEvaluateOnNewDocument',{identifier});
  await wait(`!document.querySelector('#error-banner').hidden`,'initial snapshot failure offers recovery');
  await click('#reload-btn');
  await wait(`document.querySelector('#cinematic').open&&document.querySelector('#cinematic-video').muted&&!document.querySelector('#cinematic-video').paused`,'blocked autoplay falls back to muted playback automatically');
  await check('recovering an untouched save preserves the opening and autoplay fallback',`window.__qaAutoplayBlocked&&document.querySelector('#cinematic').dataset.kind==='opening'&&document.querySelector('#train-map').childElementCount===0`);
  await cinematicReady('opening','opening.mp4');await finishVideo();await ready();
  await check('recovered opening continues into car 1',`fetch('/api/game').then(r=>r.json()).then(d=>d.game.revision===0&&d.game.location.id==='car_1'&&!document.querySelector('#cinematic').open&&document.querySelector('#error-banner').hidden)`);
 };
 const walkThroughDoor=async(target,width)=>{
  const selector='[data-hotspot="door_to_'+target+'"]';
  await wait(`!!document.querySelector(${JSON.stringify(selector)})`,'unlocked scene door to '+target);
  await check('door hotspot matches its scene and destination '+target+' '+width,`fetch('/api/game').then(r=>r.json()).then(d=>{const p=d.scene.hotspots.find(p=>p.id==='door_to_${target}');return p?.kind==='move'&&p.target==='${target}'&&p.background===d.scene.background&&p.polygon.length>=3;})`);
  await click(selector,true);await snapshot('door-to-'+target+'-'+width);
  await click(selector);await ready();
  await check('clicking the actual door moves to '+target+' '+width,`fetch('/api/game').then(r=>r.json()).then(d=>d.game.location.id==='${target}'&&d.game.status==='playing'&&!document.querySelector('#overlay').open&&document.querySelector('#scene-image').getAttribute('src')===d.scene.background)`);
 };

 if(inventoryOnly)await inventoryChecks();
 if(cinematicsOnly&&!inventoryOnly){
  await viewport(390,844);await issueName('윤슬');await openingChecks();
 }
 if(!process.argv.includes('--puzzles-only')&&!cinematicsOnly&&!doorsOnly&&!inventoryOnly){
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
 await click('#issueBtn');await openingChecks();await ready();
 await check('issued passenger name reaches the real game',`fetch('/api/game').then(r=>r.json()).then(d=>d.game.username==='윤슬'&&d.game.location.id==='car_1'&&d.game.status==='playing')`);
 await click('[data-hotspot="window"]');await wait(`document.querySelector('#overlay').dataset.view==='window'`);
 await wait(`document.querySelector('#overlay video')?.readyState>=2`);
 await check('local window video decodes and loops',`(()=>{const v=document.querySelector('#overlay video');return v.loop&&v.muted&&v.playsInline&&v.videoWidth>0;})()`);
 await click('#close-overlay');
 }
 if(!cinematicsOnly&&!inventoryOnly)for(const [width,height] of [[1440,900],[390,844]]){
  await viewport(width,height);
  for(const phase of ['nav_blocked','nav_conversation','nav_crew_locked','dark']){
   await seed(phase);
   await check('gated scene has no movement door '+phase+' '+width,`!document.querySelector('[data-hotspot^="door_to_"]')`);
  }
  await seed('nav_crew');
  for(const target of ['car_2','car_3','car_4','crew'])await walkThroughDoor(target,width);
  await check('crew inner door stays inactive before engine permission '+width,`!document.querySelector('[data-hotspot^="door_to_"]')`);
  await seed('nav_engine');
  await check('car 4 door keeps its crew-room destination after engine permission '+width,`!!document.querySelector('[data-hotspot="door_to_crew"]')&&!document.querySelector('[data-hotspot="door_to_engine"]')`);
  await walkThroughDoor('crew',width);await walkThroughDoor('engine',width);
  await click('#train-map [data-location="crew"]');await ready();
  await check('engine returns through the crew room on the minimap '+width,`fetch('/api/game').then(r=>r.json()).then(d=>d.game.location.id==='crew'&&!!document.querySelector('[data-hotspot="door_to_engine"]'))`);
 }
 if(!doorsOnly&&!inventoryOnly){
 // Pull the emergency lever through the real service and enter the crew room.
 const shadowClick=async selector=>{
  await wait(`(()=>{const r=document.querySelector('.puzzle-host')?.shadowRoot;return r&&[...r.querySelectorAll('link')].every(l=>!!l.sheet)&&[...r.querySelectorAll('img')].every(i=>i.complete&&i.naturalWidth);})()`,'puzzle stylesheet and artwork');
  await evaluate(`document.fonts.ready.then(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))))`);
  const p=await evaluate(`(()=>{const root=document.querySelector('.puzzle-host').shadowRoot,el=root.querySelector(${JSON.stringify(selector)});el.scrollIntoView({block:'center'});const r=el.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2;if(!el.contains(root.elementFromPoint(x,y)))throw new Error('Puzzle control is covered: '+${JSON.stringify(selector)});return{x,y};})()`);
  await call('Input.dispatchMouseEvent',{type:'mouseMoved',...p});await call('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...p});await call('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...p});
 };
 const puzzle=`document.querySelector('.puzzle-host')?.shadowRoot`;
 if(!cinematicsOnly)for(const [width,height] of [[1440,900],[390,844]]){
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
 // Validate real dial mechanics, confirmation cancellation and both video endings.
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
   await check('correct control immediately ends in the engine room',`fetch('/api/game').then(r=>r.json()).then(d=>d.game.attempts===0&&d.game.status==='good'&&d.game.location.id==='engine'&&document.querySelector('#send-btn').disabled)`);
  }else{
   await check('wrong final control spends exactly one attempt and opens bad ending',`fetch('/api/game').then(r=>r.json()).then(d=>d.game.attempts===0&&d.game.status==='bad'&&d.game.reason==='wrong_control'&&document.querySelector('#send-btn').disabled)`);
  }
  await check('minimap contains only the six connected train rooms '+width,`(()=>{const rooms=[...document.querySelectorAll('#train-map [data-location]')].map(b=>b.dataset.location);return rooms.length===6&&['car_1','car_2','car_3','car_4','crew','engine'].every(id=>rooms.includes(id));})()`);
  const ending=correct?'good':'bad';
  await cinematicReady(ending,ending+'-ending.mp4');
  await check('ending replaces the newspaper presentation '+ending,`!document.querySelector('.ending-paper')&&!document.querySelector('#overlay').open&&!document.querySelector('#cinematic-skip')`);
  await call('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
  await call('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
  await check('Escape preserves the '+ending+' ending',`document.querySelector('#cinematic').open`);
  await finishVideo();
  await wait(`document.querySelector('#overlay').open&&document.querySelector('#overlay').dataset.view==='ending-complete'`);
  await check(ending+' exposes restart only after the native ending completes',`!document.querySelector('#cinematic').open&&!document.querySelector('#cinematic-video').hasAttribute('src')&&document.querySelector('#cinematic-video').readyState===0&&!!document.querySelector('#ending-restart')&&document.querySelector('#send-btn').disabled`);
  await check(ending+' completion preserves the saved outcome',`fetch('/api/game').then(r=>r.json()).then(d=>d.game.status==='${ending}'&&d.game.attempts===0)`);
 }
 await click('#ending-restart');
 await cinematicReady('opening','opening.mp4');
 await check('ending restart starts a new opening before gameplay',`fetch('/api/game').then(r=>r.json()).then(d=>d.game.revision===0&&d.game.location.id==='car_1'&&d.game.status==='playing'&&d.game.attempts===null&&!d.game.clock_running)`);
 await finishVideo();await ready();
 await check('a completed new opening begins a fresh car 1 game',`fetch('/api/game').then(r=>r.json()).then(d=>d.game.location.id==='car_1'&&d.game.status==='playing'&&d.game.attempts===null&&!d.game.clock_running&&!document.querySelector('#cinematic').open)`);
 await openingRecoveryChecks();
 }
 await check('no failed game or asset responses',networkErrors.length===0);
 await check('no browser exceptions',errors.length===0);
 console.log(JSON.stringify({passed:checks.length,gameRoot,artifacts:out},null,2));
}catch(error){errors.push(String(error.stack||error));console.error(error.stack||error);await captureFailure?.().catch(()=>{});process.exitCode=1;}
finally{
 fs.writeFileSync(path.join(out,'result.json'),JSON.stringify({gameRoot,checks,errors,networkErrors,...(errors.length?{serverLog}: {})},null,2));
 if(inventoryMetrics.length)fs.writeFileSync(path.join(out,'inventory-metrics.json'),JSON.stringify(inventoryMetrics,null,2));
 socket?.close();await stopChild(browser);await stopChild(server);
 const resolvedOut=fs.realpathSync(out),resolvedProfile=fs.realpathSync(chromeProfile);
 if(resolvedProfile.startsWith(resolvedOut+path.sep)&&path.basename(resolvedProfile).startsWith('chrome-'))fs.rmSync(resolvedProfile,{recursive:true,force:true,maxRetries:8,retryDelay:150});
}

