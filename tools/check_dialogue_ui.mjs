// Run: node tools/check_dialogue_ui.mjs [--baseline | --live-api]
// Uses an isolated save; --live-api explicitly enables up to 16 paid API calls.
// Default mode stays offline. No browser helper scrolls.
// Set DIALOGUE_QA_CHROME / DIALOGUE_QA_PYTHON to override discovered executables.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const output = path.join(root, '.local', 'dialogue-ui-qa', String(Date.now()));
fs.mkdirSync(output, {recursive: true});
const chromeProfile = fs.mkdtempSync(path.join(output, 'chrome-'));
const baseline = process.argv.includes('--baseline') || !!process.env.DIALOGUE_UI_BASELINE_ZIP;
const liveApi = process.argv.includes('--live-api');
const viewports = [[1440, 900], [1366, 768], [1024, 768], [768, 1024], [390, 844], [320, 568]];
const checks = [], browserErrors = [], pending = new Map(), eventWaiters = new Set();
let modelStats = null;
let server, browser, socket, nextId = 0, sessionId;
let serverLog = '';

function chromeExecutable() {
  if (process.env.DIALOGUE_QA_CHROME) return process.env.DIALOGUE_QA_CHROME;
  const cache = path.join(process.env.LOCALAPPDATA || os.homedir(), 'ms-playwright');
  const folders = fs.existsSync(cache) ? fs.readdirSync(cache).filter(name => /^chromium-\d+$/.test(name)).sort((a, b) => Number(b.split('-')[1]) - Number(a.split('-')[1])) : [];
  const candidates = folders.map(name => path.join(cache, name, 'chrome-win64', 'chrome.exe'));
  candidates.push(path.join(process.env.PROGRAMFILES || 'C:/Program Files', 'Google/Chrome/Application/chrome.exe'));
  const found = candidates.find(candidate => fs.existsSync(candidate));
  if (!found) throw new Error('Chrome not found. Set DIALOGUE_QA_CHROME to an installed Chromium executable.');
  return found;
}

function websocketClass() {
  if (globalThis.WebSocket) return globalThis.WebSocket;
  const require = createRequire(import.meta.url);
  try { return require('ws'); } catch {}
  const cache = path.join(process.env.LOCALAPPDATA || os.homedir(), 'npm-cache', '_npx');
  for (const folder of fs.existsSync(cache) ? fs.readdirSync(cache) : []) {
    try { return require(path.join(cache, folder, 'node_modules', 'ws')); } catch {}
  }
  throw new Error('Use Node 22+ or an existing ws package. This check never installs dependencies.');
}

function processLine(child, stream, pattern, label) {
  return new Promise((resolve, reject) => {
    let buffer = '';
    const finish = (error, value) => {
      clearTimeout(timer);
      stream.off('data', onData); child.off('error', onError); child.off('exit', onExit);
      error ? reject(error) : resolve(value);
    };
    const onData = chunk => { buffer += chunk; const match = buffer.match(pattern); if (match) finish(null, match[1]); };
    const onError = error => finish(error);
    const onExit = code => finish(new Error(label + ' exited ' + code + '\n' + serverLog));
    const timer = setTimeout(() => finish(new Error(label + ' startup timeout\n' + serverLog)), 20000);
    stream.on('data', onData); child.once('error', onError); child.once('exit', onExit);
  });
}

function rejectPending(error) {
  for (const entry of pending.values()) { clearTimeout(entry.timer); entry.reject(error); }
  pending.clear();
  for (const waiter of [...eventWaiters]) waiter.finish(error);
}

function cdp(method, params = {}, attachedSession = sessionId) {
  return new Promise((resolve, reject) => {
    const id = ++nextId;
    const timer = setTimeout(() => { pending.delete(id); reject(new Error('CDP timeout: ' + method)); }, 20000);
    pending.set(id, {resolve, reject, timer});
    try { socket.send(JSON.stringify({id, method, params, ...(attachedSession ? {sessionId: attachedSession} : {})})); }
    catch (error) { clearTimeout(timer); pending.delete(id); reject(error); }
  });
}

function nextEvent(method) {
  return new Promise((resolve, reject) => {
    const entry = {method, sessionId, finish(error, value) {
      clearTimeout(timer); eventWaiters.delete(entry); error ? reject(error) : resolve(value);
    }};
    const timer = setTimeout(() => entry.finish(new Error('CDP event timeout: ' + method)), 20000);
    eventWaiters.add(entry);
  });
}

async function evaluate(expression) {
  const result = await cdp('Runtime.evaluate', {expression, awaitPromise: true, returnByValue: true});
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
  return result.result.value;
}

async function until(expression, label) {
  const deadline = Date.now() + (liveApi ? 60000 : 15000);
  while (Date.now() < deadline) {
    if (await evaluate(expression)) return;
    await new Promise(resolve => setTimeout(resolve, 60));
  }
  throw new Error('Timeout: ' + label + '\n' + JSON.stringify(await evaluate(`({url:location.href,error:document.querySelector('#error-text')?.textContent,loading:document.querySelector('#scene-loading')?.hidden,save:document.querySelector('#save-status')?.textContent})`)));
}

async function settle() {
  await until(`document.readyState==='complete'&&document.querySelector('#scene-loading')?.hidden&&document.querySelector('#save-status')?.textContent==='기록 보관됨'`, 'game ready');
  await evaluate(`document.fonts.ready.then(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))).then(()=>true)`);
}

async function navigate(url) {
  const loaded = nextEvent('Page.loadEventFired');
  await Promise.all([loaded, cdp('Page.navigate', {url})]);
  await settle();
}

async function resize(width, height) {
  await cdp('Emulation.setDeviceMetricsOverride', {width, height, deviceScaleFactor: 1, mobile: width < 601});
  await evaluate(`new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>requestAnimationFrame(resolve))))`);
}

async function screenshot(name) {
  const result = await cdp('Page.captureScreenshot', {format: 'png', captureBeyondViewport: false});
  fs.writeFileSync(path.join(output, name.replace(/[^a-zA-Z0-9_-]/g, '-') + '.png'), Buffer.from(result.data, 'base64'));
}

async function beforeEntry(label) {
  const detail = await evaluate(`(()=>({scroll:[scrollX,scrollY],viewport:[innerWidth,innerHeight],elements:['.scene-frame','.console-main','#user-message','#choice-list'].map(selector=>{const element=document.querySelector(selector),r=element.getBoundingClientRect();return{selector,hidden:element.hidden,rect:{x:r.x,y:r.y,width:r.width,height:r.height}};})}))()`);
  checks.push({label, pass: true, detail});
  if (baseline) await screenshot(label);
}

async function click(selector, label) {
  // Only click an already visible, unobstructed point. Never scroll the page.
  const point = await evaluate(`(()=>{
    const element=document.querySelector(${JSON.stringify(selector)});
    if(!element)throw new Error('Missing control: '+${JSON.stringify(label || selector)});
    const r=element.getBoundingClientRect(),left=Math.max(0,r.left),top=Math.max(0,r.top),right=Math.min(innerWidth,r.right),bottom=Math.min(innerHeight,r.bottom);
    if(element.disabled||right<=left||bottom<=top)throw new Error('Control is outside the viewport: '+${JSON.stringify(label || selector)});
    const fractions=[.5,.3,.7,.1,.9,.2,.4,.6,.8,.95,.05];
    for(const fy of fractions)for(const fx of fractions){const x=left+(right-left)*fx,y=top+(bottom-top)*fy;if(element.contains(document.elementFromPoint(x,y)))return{x,y};}
    throw new Error('Control is covered: '+${JSON.stringify(label || selector)});
  })()`);
  await cdp('Input.dispatchMouseEvent', {type: 'mouseMoved', ...point});
  await cdp('Input.dispatchMouseEvent', {type: 'mousePressed', button: 'left', clickCount: 1, ...point});
  await cdp('Input.dispatchMouseEvent', {type: 'mouseReleased', button: 'left', clickCount: 1, ...point});
}

async function surface(label, conversation = true) {
  await settle();
  const detail = await evaluate(`(()=>{
    const inspect=(element,pointer=false)=>{
      if(!element)return{missing:true,ok:false};
      const r=element.getBoundingClientRect(),style=getComputedStyle(element);
      const inside=r.width>0&&r.height>0&&r.left>=-1&&r.top>=-1&&r.right<=innerWidth+1&&r.bottom<=innerHeight+1;
      const hit=!pointer||element.contains(document.elementFromPoint(r.left+r.width/2,r.top+r.height/2));
      return{name:element.id||element.textContent.trim().slice(0,50),rect:{x:r.x,y:r.y,width:r.width,height:r.height},inside,hit,disabled:!!element.disabled,ok:inside&&hit&&!element.hidden&&!element.disabled&&style.display!=='none'&&style.visibility!=='hidden'};
    };
    const elements=[inspect(document.querySelector('.scene-frame')),inspect(document.querySelector('#user-message'),true),inspect(document.querySelector('#send-btn'),true)];
    const choices=[...document.querySelectorAll('#choice-list button')];
    elements.push(...choices.map(element=>inspect(element,true)));
    if(${conversation}){
      elements.push(inspect(document.querySelector('#dialogue-box')),inspect(document.querySelector('#dialogue-text'),true),inspect(document.querySelector('#close-dialogue'),true),inspect(document.querySelector('#end-talk'),true));
    }
    const image=document.querySelector('#scene-image'),r=image.getBoundingClientRect();
    const ratio=image.naturalWidth/image.naturalHeight,rendered=r.width/r.height;
    const ratioMatches=image.complete&&image.naturalWidth>0&&Math.abs(rendered/ratio-1)<.005;
    const dialogue=document.querySelector('#dialogue-text')?.textContent;
    return{viewport:[innerWidth,innerHeight],scroll:[scrollX,scrollY],document:[document.documentElement.scrollWidth,document.documentElement.scrollHeight],natural:[image.naturalWidth,image.naturalHeight],rendered:[r.width,r.height],ratioMatches,choices:choices.length,elements,dialogue,ok:elements.every(element=>element.ok)&&choices.length>0&&ratioMatches&&Math.abs(scrollY)<1&&document.documentElement.scrollWidth<=innerWidth+1&&(!${conversation}||!!dialogue?.trim())};
  })()`);
  checks.push({label, pass: detail.ok, detail});
  if (!detail.ok) {
    await screenshot('failed-' + label);
    throw new Error('Dialogue/input/choices do not fit together: ' + label + '\n' + JSON.stringify(detail));
  }
}

async function choose(label) {
  const index = await evaluate(`[...document.querySelectorAll('#choice-list button')].findIndex(button=>button.textContent.trim()===${JSON.stringify(label)})`);
  if (index < 0) throw new Error('Missing authored choice: ' + label);
  const previous = await evaluate(`document.querySelector('#dialogue-text').textContent`);
  await click('#choice-list button:nth-child(' + (index + 1) + ')', label);
  await until(`document.querySelector('#dialogue-text').textContent!==${JSON.stringify(previous)}&&document.querySelector('#save-status')?.textContent==='기록 보관됨'`, 'authored choice response');
  await settle();
}

async function scenario(label, callback) {
  const previousChecks = checks.length;
  try { await callback(); }
  catch (error) {
    if (!checks.slice(previousChecks).some(check => !check.pass)) checks.push({label, pass: false, error: String(error)});
    console.error('FAIL: ' + label + ': ' + error.message);
    await screenshot('scenario-' + label).catch(() => {});
  }
}

async function stopChild(child) {
  if (!child || child.exitCode !== null) return;
  await new Promise(resolve => {
    const timer = setTimeout(resolve, 5000);
    child.once('exit', () => { clearTimeout(timer); resolve(); });
    child.kill();
  });
}

try {
  const python = process.env.DIALOGUE_QA_PYTHON || path.join(root, 'runtime', 'python.exe');
  if (baseline && liveApi) throw new Error('Choose either baseline or live API mode.');
  const serverEnvironment = {...process.env};
  serverEnvironment.DIALOGUE_QA_LIVE_API = liveApi ? '1' : '0';
  if (baseline) serverEnvironment.DIALOGUE_UI_BASELINE_ZIP = process.env.DIALOGUE_UI_BASELINE_ZIP || path.join(root, 'dist', '13Fri-Windows.zip');
  server = spawn(python, ['-B', '-X', 'utf8', path.join(root, 'tools', 'dialogue_ui_server.py')], {cwd: root, env: serverEnvironment, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe']});
  server.stderr.on('data', chunk => { serverLog = (serverLog + chunk).slice(-8000); });
  const port = await processLine(server, server.stdout, /QA_PORT=(\d+)/, 'QA server');
  const base = 'http://127.0.0.1:' + port;
  browser = spawn(chromeExecutable(), ['--headless=new', '--no-first-run', '--no-default-browser-check', '--disable-background-networking', '--disable-component-update', '--disable-extensions', '--disable-breakpad', '--autoplay-policy=document-user-activation-required', '--remote-debugging-port=0', '--user-data-dir=' + chromeProfile, 'about:blank'], {windowsHide: true, stdio: ['ignore', 'ignore', 'pipe']});
  const websocketUrl = await processLine(browser, browser.stderr, /DevTools listening on (ws:\/\/\S+)/, 'Chrome');
  const Socket = websocketClass();
  socket = new Socket(websocketUrl);
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('WebSocket connection timeout')), 15000);
    socket.addEventListener('open', () => { clearTimeout(timer); resolve(); }, {once: true});
    socket.addEventListener('error', () => { clearTimeout(timer); reject(new Error('WebSocket connection failed')); }, {once: true});
  });
  socket.addEventListener('message', event => {
    const message = JSON.parse(typeof event.data === 'string' ? event.data : event.data.toString());
    if (message.id && pending.has(message.id)) {
      const entry = pending.get(message.id); pending.delete(message.id); clearTimeout(entry.timer);
      message.error ? entry.reject(new Error(JSON.stringify(message.error))) : entry.resolve(message.result);
    }
    if (message.method === 'Runtime.exceptionThrown') browserErrors.push(message.params.exceptionDetails.exception?.description || message.params.exceptionDetails.text);
    for (const waiter of [...eventWaiters]) if (message.method === waiter.method && message.sessionId === waiter.sessionId) waiter.finish(null, message.params);
  });
  socket.addEventListener('close', () => rejectPending(new Error('Chrome connection closed')));
  socket.addEventListener('error', () => rejectPending(new Error('Chrome connection failed')));
  const {targetId} = await cdp('Target.createTarget', {url: 'about:blank'}, null);
  ({sessionId} = await cdp('Target.attachToTarget', {targetId, flatten: true}, null));
  await cdp('Page.enable'); await cdp('Runtime.enable');

  for (const [width, height] of viewports) {
    const dimensions = width + 'x' + height;
    await scenario('driver-' + dimensions, async () => {
      await resize(width, height);
      await navigate(base + '/qa/dialogue?npc=driver');
      if (baseline) {
        const archivedAssets = await evaluate(`Promise.all(['/assets/js/chatbot.js','/assets/css/style.css'].map(url=>fetch(url).then(response=>response.headers.get('X-Dialogue-QA-Baseline')==='distribution-zip'))).then(results=>results.every(Boolean))`);
        if (!archivedAssets) throw new Error('Baseline assets were not served from the distribution ZIP');
      }
      await beforeEntry('driver-before-entry-' + dimensions);
      await click('[data-npc="driver"]', 'driver');
      await until(`document.querySelector('#conversation-badge')?.hidden===false&&document.querySelector('#dialogue-box')?.hidden===false`, 'driver entry');
      await surface('driver-entry-' + dimensions);
      if (baseline) return;
      for (const label of ['당장 멈추세요.', '아지산으로 가야 합니다.', '비밀번호가 뭐죠?']) {
        await choose(label); await surface('driver-choice-' + label + '-' + dimensions);
      }
      await click('#user-message'); await cdp('Input.insertText', {text: liveApi ? '현재가 몇 년이라고 알고 계신가요?' : '입력창 확인'});
      const previous = await evaluate(`document.querySelector('#dialogue-text').textContent`);
      await click('#send-btn');
      await until(`document.querySelector('#dialogue-text').textContent!==${JSON.stringify(previous)}&&document.querySelector('#user-message').value===''`, 'typed driver response');
      await surface('driver-text-' + dimensions);
      if (liveApi) {
        const correctBelief = await evaluate(`document.querySelector('#dialogue-text').textContent.includes('2016')`);
        checks.push({label: 'live driver year belief ' + dimensions, pass: correctBelief});
        if (!correctBelief) throw new Error('Driver must retain 2016 before evidence.');
      }
      const loaded = nextEvent('Page.loadEventFired');
      await Promise.all([loaded, cdp('Page.reload')]); await settle();
      await surface('driver-reloaded-' + dimensions);
      await choose('보관함에서 자료를 살펴본다.');
      await until(`document.querySelector('#overlay')?.open===true`, 'proof inventory opens');
      await click('#close-overlay');
      await until(`document.querySelector('#overlay')?.open===false`, 'proof inventory closes');
      await surface('driver-proof-inventory-closed-' + dimensions);
      await screenshot('driver-' + dimensions);
    });
  }

  if (!baseline) {
    await scenario('driver-resize-without-scroll', async () => {
      await resize(1440, 900); await navigate(base + '/qa/dialogue?npc=driver');
      await click('[data-npc="driver"]'); await settle();
      for (const [width, height] of [...viewports, [1440, 600], [1440, 480], [844, 390], [1440, 900]]) {
        await resize(width, height); await surface('active-driver-resize-' + width + 'x' + height);
      }
    });
    for (const npc of ['attendant', 'explorer', 'cleaner', 'elder']) {
      for (const [width, height] of viewports) {
        await scenario(npc + '-' + width + 'x' + height, async () => {
          // Comparison NPCs begin through the real select_npc service action;
          // exploration NPC silhouettes can lie below a short viewport.
          // Driver entry above always uses a physical pointer with no scroll.
          await resize(width, height); await navigate(base + '/qa/dialogue?npc=' + npc + '&active=1');
          await until(`document.querySelector('#conversation-badge')?.hidden===false&&document.querySelector('#dialogue-box')?.hidden===false`, npc + ' entry');
          await surface(npc + '-entry-' + width + 'x' + height);
        });
      }
    }
  }
  checks.push({label: 'zero browser runtime exceptions', pass: browserErrors.length === 0, detail: browserErrors});
  if (liveApi) {
    modelStats = await evaluate(`fetch('/qa/model-stats').then(response=>response.json())`);
    checks.push({label: 'real API interpretation and reply both completed',
      pass: modelStats.live_api && modelStats.calls.some(call=>call.kind==='interpret') && modelStats.calls.some(call=>call.kind==='reply') && modelStats.calls.every(call=>call.status==='completed'), detail: modelStats});
  }
} catch (error) {
  checks.push({label: 'test infrastructure', pass: false, error: String(error)});
  console.error(error);
} finally {
  fs.writeFileSync(path.join(output, 'checks.json'), JSON.stringify({baseline, liveApi, modelStats, checks, browserErrors}, null, 2));
  socket?.close(); rejectPending(new Error('Test finished'));
  await stopChild(browser); await stopChild(server);
  // Only remove this run's generated Chrome profile within the QA output folder.
  const resolvedOutput = fs.realpathSync(output), resolvedProfile = fs.realpathSync(chromeProfile);
  if (resolvedProfile.startsWith(resolvedOutput + path.sep) && path.basename(resolvedProfile).startsWith('chrome-')) {
    fs.rmSync(resolvedProfile, {recursive: true, force: true, maxRetries: 8, retryDelay: 150});
  }
}

const failures = checks.filter(check => !check.pass);
console.log((failures.length ? 'FAIL' : 'PASS') + ': ' + checks.length + ' checks, ' + failures.length + ' failures. Results: ' + path.join(output, 'checks.json'));
if (failures.length) process.exitCode = 1;
