"use strict";
const sceneLoading = document.getElementById('scene-loading');
function showSceneLoading(show) { if(sceneLoading) sceneLoading.hidden=!show; }
window.addEventListener('pageshow',()=>showSceneLoading(false));
if(!document.querySelector('.chat-area')) {
  document.querySelectorAll('a[href]').forEach(a=>a.addEventListener('click',e=>{
    if(!e.ctrlKey&&!e.metaKey&&e.button===0&&new URL(a.href,location.href).pathname==='/chat') showSceneLoading(true);
  }));
  document.querySelector('.boarding-form')?.addEventListener('submit',()=>showSceneLoading(true));
}
(function(){
if(!document.querySelector('.chat-area')) return;
const $ = (id) => document.getElementById(id);
const shell = document.querySelector('.chat-area');
const overlay = $('overlay');
let state = null, scene = null, busy = false, lastRequest = null, toastTimer = null;
let locationNoticeTimer = null, locationNoticeSequence = 0;
let activeHintChoice = null;
let conversationLayoutFrame = null;
let selectedDocument = null;
let inventoryPage = 0, catalogPage = 0;
const inventoryMobile = window.matchMedia('(max-width: 600px)');
let controlDraft = {destination: '', password: '0000'};
const documents = new Map();
const seenEvents = new Set();
const supportedActions = new Set(['look','move','select_npc','inspect','read_item','use_item','operate','read_report','ack_document','prepare_evidence','prepare_control','confirm','cancel','abandon','hint','disembark','end_talk','present','choose']);
let acquisitionQueue=[], acquisitionActive=false;
let acquisitionTimer=null;
const preparedImages=new Map();
function prepareImage(src) {
  if(preparedImages.has(src)) return preparedImages.get(src);
  const promise=new Promise((resolve,reject)=>{const img=new Image();img.onload=()=>{if(img.decode)img.decode().then(()=>resolve(img)).catch(()=>resolve(img));else resolve(img);};img.onerror=()=>reject(new Error('장면 이미지를 불러오지 못했습니다. 같은 요청으로 다시 시도해 주세요.'));img.src=src;});
  preparedImages.set(src,promise);promise.catch(()=>preparedImages.delete(src));return promise;
}
async function prepareScene(data,force=false) {
  const changed=force||!state||data.game.location.id!==state.location.id;
  if(changed) showSceneLoading(true);
  const surfaces=!state?['dialogue-paper','chat-input','choice-paper','hint-paper'].map(name=>prepareImage('/assets/images/ui/'+name+'.png')):[];
  await Promise.all([...surfaces,prepareImage(data.scene.background),...data.scene.people.filter(p=>p.active||!data.game.npc).map(p=>prepareImage(!p.active&&p.registration?p.registration.image:p.image)),...(data.scene.hotspots||[]).filter(p=>p.image).map(p=>prepareImage(p.image)),...(data.ui?.document?.artwork?[prepareImage(data.ui.document.artwork)]:[])]);

}
function acquisition(events) {
  for(const e of events) {const id=e.event_id||e.item.id;if(seenEvents.has(id))continue;seenEvents.add(id);acquisitionQueue.push(e.item);}
  showAcquisition();
}
function showAcquisition() {
  if(acquisitionActive||!acquisitionQueue.length)return;
  acquisitionActive=true;const item=acquisitionQueue.shift(),card=$('acquisition-notice');card.replaceChildren();
  const art=node('div','acquired-icon');art.append(inventoryArt(item));
  const copy=node('div','acquired-copy');copy.append(node('small','','소지품 획득'),node('strong','',item.name),node('span','','보관함에 보관되었습니다.'));
  const close=button('×',dismissAcquisition,'acquired-close');close.setAttribute('aria-label','획득 알림 닫기');
  card.append(art,copy,close);card.hidden=false;card.classList.add('appearing');placeAcquisition();
  clearTimeout(acquisitionTimer);acquisitionTimer=setTimeout(dismissAcquisition,4500);
}
function placeAcquisition(){const card=$('acquisition-notice');if(overlay.open){card.classList.add('in-focus');$('overlay-header-anchor')?.remove();overlay.insertBefore(card,$('overlay-body'));}else{card.classList.remove('in-focus');document.body.append(card);}}
overlay.addEventListener('close',placeAcquisition);
function dismissAcquisition(){clearTimeout(acquisitionTimer);$('acquisition-notice').hidden=true;acquisitionActive=false;showAcquisition();}

const inventoryArtwork = {
  ticket_current:'ticket-current', newspaper:'newspaper', flashlight:'flashlight',
  facility_manual:'facility-manual', elder_testimony:'elder-testimony',
  ticket_old:'ticket-old', route_report:'route-report'
};
function inventoryArt(item, cls='inventory-item-art') {
  const img=node('img',cls);
  img.src='/assets/images/inventory/'+(inventoryArtwork[item.id]||'elder-testimony')+'.png';
  img.alt=item.name||item.title||'소지품';img.draggable=false;return img;
}
function node(tag, cls = '', text = '') { const n = document.createElement(tag); if (cls) n.className = cls; if (text) n.textContent = text; return n; }
function button(text, handler, cls = '', server = false) { const b = node('button', cls, text); b.type = 'button'; if (server) { b.dataset.busyControl = '1'; b.disabled = busy; } b.addEventListener('click', handler); return b; }
function toast(text) { clearTimeout(toastTimer); $('toast').textContent = text; $('toast').hidden = false; toastTimer = setTimeout(() => { $('toast').hidden = true; }, 3800); }
function setBusy(value) { busy = value; $('overlay-body').querySelector('.puzzle-host')?.puzzle?.setBusy(busy); $('send-btn').disabled = busy || state?.status !== 'playing'; $('user-message').disabled = busy || state?.status !== 'playing'; document.querySelectorAll('[data-busy-control]').forEach(b => { b.disabled = busy || b.dataset.locked === '1'; }); $('save-status').textContent = busy ? '응답을 기다리는 중' : '기록 보관됨'; }
function setError(text, canRetry = true) { $('error-text').textContent = text; $('error-banner').hidden = false; $('retry-btn').hidden = !canRetry; if (overlay.open) { let e = $('modal-error'); if (!e) { e = node('p','error-banner'); e.id='modal-error'; $('overlay-body').prepend(e); } e.textContent = text; } }
function clearError() { $('error-banner').hidden = true; $('modal-error')?.remove(); }
async function request(url, body = null) {
  const controller = new AbortController(); const timer = setTimeout(() => controller.abort(), 60000);
  try { const res = await fetch(url, {method: body === null ? 'GET' : 'POST', credentials:'same-origin', headers: body === null ? {} : {'Content-Type':'application/json'}, body:body === null ? undefined : JSON.stringify(body), signal:controller.signal});
    let data; try { data = await res.json(); } catch { throw new Error('응답을 읽지 못했습니다. 진행 기록을 다시 불러와 주세요.'); }
    if (!res.ok) { const e = new Error(data.error?.message || '요청을 처리하지 못했습니다.'); e.code=data.error?.code; e.status=res.status; throw e; } return data;
  } catch(e) { if (e.name === 'AbortError') throw new Error('응답 대기가 길어졌습니다. 같은 요청으로 다시 시도하거나 기록을 불러와 주세요.'); throw e; }
  finally { clearTimeout(timer); }
}
async function perform(content,reuse=false) {
  if(busy||!state)return null;clearError();$('reply-status').textContent='';
  let focusComposer=false;
  const body=reuse?content:{...content,request_id:crypto.randomUUID?crypto.randomUUID():'turn_'+Date.now()+'_'+Math.random().toString(36).slice(2),revision:state.revision};
  const likelyTravel=typeof body.message==='string'&&/^(?:[1-4]호차|다음\s*칸|이전\s*칸|승무원실|기관실)(?:로|으로)?\s*(?:이동|가겠|갑니다|간다|돌아|들어갑)/.test(body.message.trim())&&!/않|안\s*가|했|다면|[?]/.test(body.message);
  const expectedTransition=likelyTravel||body.action?.type==='move'||body.action?.type==='disembark'||(body.action?.type==='confirm'&&state.confirmation?.kind==='control');
  lastRequest=body;setBusy(true);if(expectedTransition){if(overlay.open)overlay.close();showSceneLoading(true);}
  try {
    const data=await request('/api/chat',body);await prepareScene(data);apply(data,false,body);lastRequest=null;
    if(body.action?.type==='present'&&overlay.open&&!data.ui?.inventory&&!data.ui?.document&&!data.game.confirmation)overlay.close();
    if(body.message){$('user-message').value='';$('user-message').style.height='auto';}
    focusComposer=!!data.ui?.compose&&state.status==='playing'&&!overlay.open;
    if(data.ui?.ignored)$('reply-status').textContent='장면에 반영되지 않은 입력입니다.';
    return data;
  } catch(e) {setError(e.message,e.code!=='stale_state');if(e.code==='stale_state'){lastRequest=null;try{const data=await request('/api/game');await prepareScene(data);apply(data);}catch{}}return null;}
  finally{showSceneLoading(false);setBusy(false);if(focusComposer)$('user-message').focus({preventScroll:true});}
}
const act=(type,extra={}) => perform({action:{type,...extra}});
function setDialogueVisible(visible) {
  const box=$('dialogue-box');box.hidden=!visible;
  shell.classList.toggle('dialogue-open',visible);shell.dataset.dialogue=visible?'open':'closed';
  document.querySelectorAll('.person-hotspot').forEach(person=>person.setAttribute('aria-expanded',String(visible&&person.dataset.npc===state?.npc)));
}
function updateDialogue(data, interaction, previous) {
  const action=interaction?.action?.type;
  const reply=typeof data.reply==='string'?data.reply.trim():'';
  const entry=state.history?.at(-1);
  // A saved conversation has no triggering action, but its last NPC reply still belongs on screen.
  const restoring=!interaction&&!!state.npc&&entry?.role==='npc'&&entry.npc===state.npc&&entry.text===data.reply;
  const traveled=previous&&previous.location.id!==state.location.id;
  const endedTalk=!state.npc&&reply.startsWith('대화를 마치고 주변으로 시선을 돌렸다.');
  const exploring=action==='look'||action==='end_talk'||action==='hint'||(action==='move'&&interaction.action.target===state.location.id);
  if((!interaction&&!restoring)||data.ui?.ignored||!reply||traveled||endedTalk||exploring||state.status!=='playing') {
    setDialogueVisible(false);return;
  }
  const speaker=entry?.role!=='user'&&entry?.text===data.reply?entry.speaker:'차내';
  $('speaker-name').textContent=speaker;
  // '차내' is narration (wrapped in parentheses); any other speaker is spoken dialogue.
  $('dialogue-box').classList.toggle('narration',speaker==='차내');
  $('dialogue-text').replaceChildren(...(speaker==='차내'?[reply]:dialogueParts(reply)));$('dialogue-text').scrollTop=0;
  setDialogueVisible(true);
}
// A character line may mix narration with quoted speech: “…” is spoken, the rest is narration.
// Lines without quotes are spoken as a whole.
function dialogueParts(text) {
  if(!text.includes('“'))return [node('span','dialogue-speech',text)];
  return text.split(/(“[^”]*(?:”|$))/).filter(Boolean).map(part=>{
    if(part.startsWith('“'))return node('span','dialogue-speech',part);
    if(!part.trim())return part;
    const [,lead,body,trail]=part.match(/^(\s*)([\s\S]*?)(\s*)$/);
    const aside=document.createDocumentFragment();
    aside.append(lead,node('span','dialogue-aside',body),trail);
    return aside;
  });
}
function renderGuidance(data, interaction) {
  const candidate=data.ui?.hint_choice;
  activeHintChoice=interaction?.action?.type==='hint'&&!data.ui?.ignored&&state.status==='playing'&&!state.confirmation&&candidate&&typeof candidate.label==='string'&&candidate.label.trim()&&candidate.action?.type==='choose'&&typeof candidate.action.target==='string'&&candidate.action.target.startsWith('hint.')?candidate:null;
  const hint=!!activeHintChoice;
  $('hint-title').textContent=hint?'HINT · 지금 해야 할 일':'';
  $('hint-text').textContent=hint?activeHintChoice.label:'';
  $('hint-panel').hidden=!hint;
  $('hint-choice').dataset.locked=hint?'0':'1';
  $('hint-choice').dataset.choiceId=hint?activeHintChoice.id:'';
  $('hint-choice').disabled=busy||!hint;
  $('hint-btn').setAttribute('aria-expanded',String(hint));
  const choices=state.status!=='playing'||state.confirmation?[]:Array.isArray(data.ui?.choices)?data.ui.choices:Array.isArray(state.choices)?state.choices:[];
  const list=$('choice-list');list.replaceChildren();
  choices.forEach(choice=>{
    if(!choice||typeof choice!=='object'||list.childElementCount>=2)return;
    const label=typeof choice.label==='string'?choice.label.trim():typeof choice.text==='string'?choice.text.trim():'';
    const action=choice.action&&typeof choice.action==='object'&&supportedActions.has(choice.action.type)?choice.action:null;
    const message=typeof choice.message==='string'?choice.message.trim():'';
    if(!label||(!action&&(!message||message.length>2000)))return;
    const b=button('',()=>action?perform({action:{...action}}):sendText(message),'choice-button',true);
    b.append(node('span','choice-label',label));
    if(typeof choice.id==='string')b.dataset.choiceId=choice.id;
    if(choice.kind==='interaction')b.dataset.choiceKind=choice.kind;
    if(choice.disabled||state.status!=='playing'){b.disabled=true;b.dataset.locked='1';}
    list.append(b);
  });
  list.hidden=hint||!list.childElementCount;
  $('hints-and-choices').hidden=!list.childElementCount&&!hint;
  $('hints-and-choices').dataset.mode=hint?'hint':list.childElementCount?'choices':'empty';
}
function updateLocationNotice(previous) {
  $('location-name').textContent=state.location.name;
  if(previous?.location.id===state.location.id)return;
  const notice=$('location-notice'),sequence=++locationNoticeSequence;
  clearTimeout(locationNoticeTimer);notice.hidden=false;
  locationNoticeTimer=setTimeout(()=>{
    if(sequence!==locationNoticeSequence)return;
    notice.hidden=true;locationNoticeTimer=null;
  },5000);
}
function fitConversation() {
  if(conversationLayoutFrame!==null)return;
  conversationLayoutFrame=requestAnimationFrame(()=>{
    conversationLayoutFrame=null;
    const frame=document.querySelector('.scene-frame');
    if(!shell.classList.contains('conversation-active')){
      frame.style.removeProperty('--conversation-scene-width');return;
    }
    // Fit the complete native canvas above the controls. Constraining only its
    // height would stretch the background and misalign registered hotspots.
    const css=getComputedStyle(shell),map=document.querySelector('.train-map-bar');
    const console=document.querySelector('.conversation-console');
    const px=value=>parseFloat(value)||0;
    const padding=px(css.paddingTop)+px(css.paddingBottom);
    const margins=px(getComputedStyle(map).marginBottom)+px(getComputedStyle(console).marginTop);
    const viewportHeight=window.visualViewport?.height||document.documentElement.clientHeight;
    const border=getComputedStyle(frame);
    const borderHeight=px(border.borderTopWidth)+px(border.borderBottomWidth);
    const borderWidth=px(border.borderLeftWidth)+px(border.borderRightWidth);
    const available=Math.max(160,viewportHeight-document.querySelector('.game-header').offsetHeight-padding-map.offsetHeight-console.offsetHeight-margins-borderHeight-2);
    const ratio=String(scene?.aspect_ratio||'3 / 2').split('/').map(Number);
    const aspect=ratio.length===2&&ratio.every(n=>Number.isFinite(n)&&n>0)?ratio[0]/ratio[1]:1.5;
    frame.style.setProperty('--conversation-scene-width',(available*aspect+borderWidth)+'px');
  });
}
function apply(data, force = false, interaction = null) {
  if(!data?.game || !data?.scene) throw new Error('진행 상태 응답이 올바르지 않습니다.');
  if(!force && state && data.game.revision < state.revision) return;
  const previous=state;
  state=data.game; scene=data.scene;
  shell.classList.toggle('conversation-active',!!state.npc&&state.status==='playing');
  updateLocationNotice(previous);
  $('scene-world').style.aspectRatio=scene.aspect_ratio||'3 / 2';
  const bg=$('scene-image');if(bg.getAttribute('src')!==scene.background)bg.src=scene.background;
  bg.alt=state.location.name+'의 현재 장면';
  $('darkness').hidden=scene.light_mode==='normal';$('darkness').classList.toggle('flashlight-mask',scene.light_mode==='flashlight');if(state.npc){$('darkness').style.setProperty('--beam-x','50%');$('darkness').style.setProperty('--beam-y','48%');}
  $('scene-world').dataset.mode=state.npc?'conversation':'exploration';
  $('scene-caption').textContent=scene.dark?'불이 꺼져 아무것도 보이지 않는다.':state.status!=='playing'?'끝나지 않던 밤의 기록.':'';
  const layer=$('character-layer');layer.replaceChildren();
  const people=state.npc?scene.people.filter(p=>p.active):scene.people;
  people.forEach(p=>{
    if(!p.active&&p.registration){registeredHotspot(layer,p,()=>act('select_npc',{target:p.id}),true);return;}
    const b=button('',()=>act('select_npc',{target:p.id}),'person-hotspot'+(p.active?' talking':''),true);b.dataset.npc=p.id;
    b.setAttribute('aria-label',p.name+'에게 말 걸기');b.setAttribute('aria-controls','dialogue-box');b.title=p.name+' · 대화 시작';
    const bounds=p.active?[31,3,38,97]:p.bounds;place(b,bounds);
    const img=node('img','character-sprite');img.src=p.image;img.alt=p.name;img.draggable=false;
    const label=node('span','hotspot-label',p.name+' · 대화');b.append(img,label);layer.append(b);
  });
  $('conversation-badge').hidden=!state.npc;$('active-person').textContent=state.npc?(scene.people.find(p=>p.id===state.npc)?.name||'인물')+'와 대화 중':'';
  $('interaction-guide').textContent=state.npc?'채팅으로 대화하세요. 대화를 마치려면 위의 ‘대화 마치기’를 누르세요.':'빛나는 지점에 커서를 올려 대상을 확인하세요. 채팅으로도 조사할 수 있습니다.';
  updateDialogue(data,interaction,previous);renderGuidance(data,interaction);
  $('current-target').textContent=state.npc? (scene.people.find(p=>p.id===state.npc)?.name || '상대')+'에게 말하거나 주변에 행동하기':'현재 장면에 행동하기';
  $('item-count').textContent=state.inventory.length; $('bag-btn').classList.toggle('bag-pulse',!!state.bag_hint);
  renderLinearMap();renderSceneActions();
  acquisition((data.events||[]).filter(e=>e.type==='item_acquired'));
  if(state.status!=='playing') openEnding();
  else if(state.confirmation) openConfirmation();
  else if(data.ui?.document) { selectedDocument=data.ui.document;documents.set(selectedDocument.id,selectedDocument);openInventory(selectedDocument); }
  else if(data.ui?.notice) openNotice();
  else if(data.ui?.window_video) openWindowVideo();
  else if(data.ui?.inventory) openInventory();
  else if(data.ui?.control) openControl();
  else if(data.ui?.lever) openLever();
  else if(overlay.open && overlay.dataset.view==='lever') openLever();
  setBusy(busy);
  fitConversation();
}
function place(el,bounds){const [x,y,w,h]=bounds;Object.assign(el.style,{left:x+'%',top:y+'%',width:w+'%',height:h+'%'});}
function registeredHotspot(layer,p,handler,person=false){
  // Art and background use the same full canvas, with a shared origin and
  // scale. The silhouette clips only the hit area; it never clips the glow.
  const art=p.registration;
  if(art.background!==scene.background)return;
  const group=node('div','registered-hotspot');
  const b=button('',handler,(person?'person-hotspot':'world-hotspot')+' registered-hit',true);
  b.style.clipPath='polygon('+art.polygon.map(([x,y])=>x+'% '+y+'%').join(',')+')';
  const label=person?p.name+' · 대화':p.label;
  b.setAttribute('aria-label',person?p.name+'에게 말 걸기':label);
  if(person){b.dataset.npc=p.id;b.setAttribute('aria-controls','dialogue-box');b.setAttribute('aria-expanded','false');}
  else b.dataset.hotspot=p.id;
  // Mask the original texture after sampling it at the background's scale.
  // Resampling a transparent cutout directly can darken its boundary pixels.
  const img=node('img','registered-art');img.src=art.background;img.alt='';img.draggable=false;
  img.style.maskImage='url("'+art.image+'")';
  img.setAttribute('aria-hidden','true');
  const visual=node('div','registered-visual');visual.append(img);
  const caption=node('span','hotspot-label registered-label',label);
  const [x,y,w]=art.bounds;
  caption.style.left=Math.max(12,Math.min(88,x+w/2))+'%';caption.style.top=Math.max(11,y-4)+'%';
  group.append(b,visual,caption);layer.append(group);
}
function renderLinearMap(){
  const box=$('train-map');box.replaceChildren();
  const canvas=node('div','train-map-canvas'),art=node('img','train-map-art');
  art.src='/assets/images/ui/train-route.png';art.alt='';art.draggable=false;art.setAttribute('aria-hidden','true');canvas.append(art);
  const sections={car_1:[0,14.5],car_2:[14.5,14.5],car_3:[29,13],car_4:[42,13.5],crew:[55.5,14],platform:[69.5,13.5],engine:[83,17]};
  const order=['car_1','car_2','car_3','car_4','crew','platform','engine'];
  const stops=[...state.map].sort((a,b)=>order.indexOf(a.id)-order.indexOf(b.id));
  stops.forEach((p,index)=>{
    const status=p.current?'현재 위치':!p.open?'잠김':p.visited?'다녀온 곳':'이동 가능';
    const b=button('',async()=>{if(overlay.open)overlay.close();await act(p.id==='platform'?'disembark':'move',{target:p.id});},'linear-stop train-carriage'+(p.current?' current':p.visited?' visited':'')+(!p.open?' locked':''),true);
    const label=p.id==='platform'?'출입구':p.name;
    const description=p.id==='platform'?label+' · '+p.name:p.id==='crew'?'승무원실 · 4호차에서 연결':p.name;
    b.dataset.location=p.id;b.setAttribute('aria-current',p.current?'location':'false');b.setAttribute('aria-label',description+' · '+status);b.title=description+' · '+status;
    const [left,width]=sections[p.id]||[index*100/state.map.length,100/state.map.length];
    b.style.left=left+'%';b.style.width=width+'%';
    b.append(node('span','stop-name',label),node('span','stop-state',status));
    const canDisembark=p.id==='platform'&&state.controls.exit;
    if(!p.open||(p.current&&!canDisembark)||state.status!=='playing'){b.disabled=true;b.dataset.locked='1';}canvas.append(b);
  });
  box.append(canvas);
}
function renderSceneActions(){
 const layer=$('scene-hotspots');layer.replaceChildren();
 if(state.status!=='playing')return;
 (scene.hotspots||[]).forEach(p=>{const interact=()=>{
   if(p.kind==='focus'){if(p.target==='door')openLever();else if(p.target==='control'){if(state.controls.control)openControl();else if(state.controls.proof)openInventory();else toast('먼저 기관사에게 장치에 관해 물어보세요.');}}
   else act(p.kind,{target:p.target});
 };
 if(p.registration){registeredHotspot(layer,p,interact);return;}
 const b=button('',interact,'world-hotspot '+(p.image?'art-hotspot ':'')+(p.appearance||''),true);b.dataset.hotspot=p.id;b.setAttribute('aria-label',p.label);b.title=p.label;place(b,p.bounds);
 if(p.image){const img=node('img','hotspot-art');img.src=p.image;img.alt='';img.draggable=false;b.append(img,node('span','hotspot-label',p.label));layer.append(b);return;}
 const outline=document.createElementNS('http://www.w3.org/2000/svg','svg');outline.setAttribute('viewBox','0 0 100 100');outline.setAttribute('preserveAspectRatio','none');outline.setAttribute('aria-hidden','true');const rect=document.createElementNS('http://www.w3.org/2000/svg','rect');for(const [k,v] of Object.entries({x:2,y:2,width:96,height:96,rx:4}))rect.setAttribute(k,String(v));outline.append(rect);
 b.append(outline,node('span','hotspot-dot',''),node('span','hotspot-label',p.label));
 if(p.appearance==='paper')b.append(node('span','notice-mark','안내문'));layer.append(b);
 });
}
function stopOverlayMedia(){
  $('overlay-body').querySelectorAll('video').forEach(video=>{video.pause();video.removeAttribute('src');video.querySelectorAll('source').forEach(source=>source.removeAttribute('src'));video.load();});
}
function openNotice(){
  if(state?.location.id!=='car_1')return;
  const body=openOverlay('기관실 안내문','notice','ONBOARD NOTICE');
  const page=node('figure','notice-art-view'),img=node('img');
  img.src='/assets/images/car1/notice.png';img.alt='Warning: 열차의 정차는 기관실에서만 가능';
  page.append(img);body.append(page);
}
function openWindowVideo(){
  if(state?.location.id!=='car_1')return;
  const body=openOverlay('차창 밖','window','13-Fri · NIGHT VIEW');
  const frame=node('div','window-video-view'),video=node('video'),status=node('p','window-video-status');
  video.controls=true;video.loop=true;video.autoplay=true;video.muted=true;video.playsInline=true;video.preload='auto';
  video.setAttribute('aria-label','반복되는 열차 밖의 밤 풍경');video.setAttribute('playsinline','');
  for(const [ext,type] of [['webm','video/webm'],['mp4','video/mp4']]){const source=node('source');source.src='/assets/videos/car1-window-loop.'+ext;source.type=type;video.append(source);}
  video.addEventListener('error',()=>{status.textContent='영상을 재생하지 못했습니다. 창을 닫고 다시 열어 주세요.';});
  frame.append(video,status);body.append(frame);
  video.play().catch(()=>{if(video.isConnected)status.textContent='재생 버튼을 눌러 창밖을 살펴보세요.';});
}
function openOverlay(title, view, eyebrow='13-Fri · INVESTIGATION') { stopOverlayMedia();overlay.dataset.view=view; $('overlay-title').textContent=title; $('overlay-eyebrow').textContent=eyebrow; $('overlay-body').replaceChildren(); if(!overlay.open) overlay.showModal();placeAcquisition(); return $('overlay-body'); }
function pendingReport(){return overlay.open&&overlay.dataset.view==='inventory'&&selectedDocument?.id==='route_report'&&state?.inventory.some(item=>item.id==='route_report'&&!item.read);}
async function confirmReport(close=false){const data=await act('ack_document',{target:'route_report'});if(data&&close)overlay.close();return data;}
function closeOverlay() { if(busy && (overlay.dataset.view==='confirm'||pendingReport())) return; if(pendingReport()){confirmReport(true);return;} if(overlay.dataset.view==='confirm' && state?.confirmation) { act('cancel').then(data=>{if(data) overlay.close();}); } else {stopOverlayMedia();overlay.close();} }
function paperAction(label, handler, art, cls = '', server = true) {
  const b=button('',handler,'paper-action '+cls,server);
  b.setAttribute('aria-label',label);
  const image=node('img');image.src='/assets/images/inventory/actions/'+art+'.png';image.alt=label;image.draggable=false;
  b.append(image);return b;
}
function inventoryPager(parent,index,count,onPage) {
  if(count<2)return;
  const nav=node('nav','inventory-pager');nav.setAttribute('aria-label','소지품 페이지');
  const previous=paperAction('이전 페이지',()=>onPage(index-1),'previous');
  const next=paperAction('다음 페이지',()=>onPage(index+1),'next');
  for(const [b,locked] of [[previous,index===0],[next,index===count-1]])if(locked){b.disabled=true;b.dataset.locked='1';}
  nav.append(previous,node('span','inventory-page-number',String(index+1)+' / '+String(count)),next);parent.append(nav);
}
function openInventory(doc = null, keepCatalogPage = false) {
  if(!state) return;
  const selected=doc && state.inventory.some(i=>i.id===doc.id)?doc:null;
  selectedDocument=selected;
  const body=openOverlay('보관함','inventory','INVENTORY · 모은 물건과 조사 기록');
  overlay.dataset.inventoryMode=selected?'detail':'overview';
  if(!selected){
    const book=node('section','inventory-overview');book.setAttribute('aria-label','낡은 수집품 기록장');
    book.append(node('h3','visually-hidden','INVENTORY · 소지품'));
    const grid=node('div','inventory-grid');grid.setAttribute('aria-label','소지품 목록');
    const capacity=inventoryMobile.matches?6:8,count=Math.max(1,Math.ceil(state.inventory.length/capacity));
    inventoryPage=Math.max(0,Math.min(inventoryPage,count-1));
    state.inventory.slice(inventoryPage*capacity,(inventoryPage+1)*capacity).forEach(item=>{
      const card=button('',()=>openItem(item.id),'inventory-card',true);card.dataset.itemId=item.id;
      const mount=node('span','inventory-photo-mount');mount.append(inventoryArt(item));
      const frame=node('img','inventory-mount-art');frame.src='/assets/images/inventory/photo-mount.png';frame.alt='';frame.draggable=false;mount.append(frame);
      card.append(mount,node('strong','',item.name));grid.append(card);
    });
    if(!state.inventory.length)grid.append(node('p','inventory-empty','아직 모은 물건이 없습니다.'));
    book.append(grid);inventoryPager(book,inventoryPage,count,index=>{inventoryPage=index;openInventory();});body.append(book);return;
  }
  const book=node('div','inventory-detail'),catalog=node('aside','inventory-catalog');
  const back=paperAction('소지품 펼쳐 보기',async()=>{
    if(pendingReport()&&!(await confirmReport()))return;
    openInventory();
  },'inventory-back','inventory-back');
  const list=node('nav','item-list');list.setAttribute('aria-label','소지품 목록');
  const capacity=inventoryMobile.matches?3:5,count=Math.max(1,Math.ceil(state.inventory.length/capacity));
  if(!keepCatalogPage)catalogPage=Math.floor(state.inventory.findIndex(item=>item.id===selected.id)/capacity);
  catalogPage=Math.max(0,Math.min(catalogPage,count-1));
  state.inventory.slice(catalogPage*capacity,(catalogPage+1)*capacity).forEach(item=>{
    const row=button('',()=>openItem(item.id),'item-row'+(selected.id===item.id?' selected':''),true);
    row.dataset.itemId=item.id;row.setAttribute('aria-current',selected.id===item.id?'true':'false');
    const mount=node('span','inventory-list-mount');mount.append(inventoryArt(item));
    row.append(mount,node('span','',item.name));list.append(row);
  });
  catalog.append(back,list);
  inventoryPager(catalog,catalogPage,count,index=>{catalogPage=index;openInventory(selected,true);});
  const spread=node('div','inventory-spread'),object=node('figure','inventory-object'),page=node('article','book-page');
  const item=state.inventory.find(i=>i.id===selected.id);
  object.append(inventoryArt(item,'inventory-object-art'),node('figcaption','visually-hidden',item.name));
  renderDocument(page,selected);spread.append(object,page);book.append(catalog,spread);body.append(book);
}
inventoryMobile.addEventListener('change',()=>{if(overlay.open&&overlay.dataset.view==='inventory')openInventory(selectedDocument);});
async function openItem(id) {
  if(busy) return;
  if(pendingReport()&&id!=='route_report'&&!(await confirmReport()))return;
  if(state.status!=='playing') { try { const data=await request('/api/item/'+encodeURIComponent(id));openInventory(data.document); }catch(e){setError(e.message,false);} return; }
  await act('read_item',{target:id});
}
function renderDocument(page,doc) {
  const record=node('img','inventory-record-image');
  record.src=doc.artwork||'/assets/images/inventory/records/'+doc.id.replaceAll('_','-')+'.png';
  record.alt=[doc.title,...(doc.paragraphs||[]),...(doc.fields||[]).map(([key,value])=>key+': '+value)].join('\n');
  record.draggable=false;page.append(record);
  const actions=node('div','document-actions');
  if(state.status==='playing') {
    if(doc.id==='route_report'&&!state.inventory.find(item=>item.id==='route_report')?.read)actions.append(paperAction('보고서 내용 확인',()=>confirmReport(true),'confirm-report'));
    if(doc.id==='flashlight')actions.append(paperAction('손전등 사용',async()=>{if(await act('use_item',{target:doc.id}))overlay.close();},'use-flashlight'));
    if(doc.id==='ticket_old' && state.location.id==='car_3') {
      const returned=state.inventory.find(i=>i.id==='ticket_old')?.name.includes('조사 기록');
      actions.append(paperAction(returned?'노인에게 조사 기록 보여주기':'노인에게 원본 돌려드리기',()=>act('present',{target:'ticket_old',recipient:'elder'}),returned?'show-ticket-record':'return-ticket'));
    }
    if(doc.id==='route_report' && state.location.id==='car_4')actions.append(paperAction('승무원에게 보고서 보여주기',()=>act('present',{target:'route_report',recipient:'attendant'}),'show-route-report'));
    if(state.controls.proof)actions.append(paperAction('이 물건을 최종 증거로 제출',()=>act('prepare_evidence',{target:doc.id}),'submit-evidence','danger-action'));
  }
  page.dataset.actionCount=String(actions.childElementCount);
  if(actions.childElementCount)page.append(actions);
}
function openMap() {
  if(!state)return;const body=openOverlay('열차 안내도','map','TRAIN MAP · 현재 위치와 연결');const sheet=node('div','map-sheet');sheet.append(node('p','','방문한 장소로 돌아가 놓친 기록을 확인할 수 있습니다. 잠긴 구역은 조건을 충족해야 진입할 수 있습니다.'));
  const grid=node('div','map-nodes');state.map.forEach(p=>{const b=button(p.name,async()=>{const d=await act('move',{target:p.id});if(d&&d.game.location.id===p.id)overlay.close();},'map-node'+(p.current?' current':''),true);if(!p.open||state.status!=='playing'){b.disabled=true;b.dataset.locked='1';}b.append(node('span','',p.current?'현재 위치':p.open?(p.visited?'방문한 장소':'이동 가능'):'아직 진입할 수 없음'));grid.append(b);});sheet.append(grid,node('p','map-foot','1호차 ↔ 2호차 ↔ 3호차 ↔ 4호차 / 4호차에서 승무원실과 기관실로 연결'));body.append(sheet);
}
function openHistory() { if(!state)return;const body=openOverlay('대화 기록','history','CONVERSATION · 실제로 오간 이야기');const list=node('div','history-list');state.history.forEach(h=>{const r=node('article','history-row '+h.role);r.append(node('strong','',h.speaker),node('p','',h.text));if(h.record){const d=node('details');d.append(node('summary','','대화에서 확인한 사실'),node('p','',h.record));r.append(d);}list.append(r);});body.append(list);list.scrollTop=list.scrollHeight; }
function openJournal() {if(!state)return;const body=openOverlay('조사 기록','journal','FIELD NOTES · 확인한 사실');const list=node('div','journal-list');(state.journal.length?state.journal:['아직 확인한 단서가 없습니다.']).forEach(t=>list.append(node('p','journal-entry',t)));body.append(list);}
function puzzleHost(body) {
  const host=node('div','puzzle-host');
  if(document.documentElement.classList.contains('reduced-motion'))host.dataset.reducedMotion='';
  body.append(host);return host;
}
function openLever() {
  if(!state||state.location.id!=='car_4')return;
  const existing=overlay.open&&overlay.dataset.view==='lever'&&$('overlay-body').querySelector('.puzzle-host');
  if(existing?.puzzle){existing.puzzle.update(state.door);return;}
  const body=openOverlay('승무원실 출입문','lever','EMERGENCY ACCESS · 수동 조작');
  const host=puzzleHost(body);
  window.TrainPuzzles.mountLever(host,{
    door:state.door,
    onOperate:target=>act('operate',{target}),
    onInventory:()=>openInventory(),
    onEnter:async()=>{const data=await act('move',{target:'crew'});if(data?.game.location.id==='crew')overlay.close();}
  }).setBusy(busy);
}
function openControl() {
  if(!state?.controls.control)return;
  const body=openOverlay('분기기 제어 장치','control','CONTROL PANEL · 마지막 입력');
  window.TrainPuzzles.mountDial(puzzleHost(body),{
    draft:controlDraft,attempts:state.attempts,
    onChange:draft=>{controlDraft=draft;},
    onSubmit:values=>act('prepare_control',values)
  }).setBusy(busy);
}
function openConfirmation() {
  const c=state?.confirmation;if(!c)return;const body=openOverlay(c.title,'confirm','FINAL CONFIRMATION · 되돌릴 수 없는 선택');const content=node('div','modal-content');content.append(node('p','',c.text));
  if(c.kind==='control'){const values=node('div','confirmation-values');values.append(node('span','','목적지: '+c.destination),node('span','','비밀번호: '+c.password));content.append(values);}
  if(c.kind==='evidence'){const values=node('div','confirmation-values',c.title);content.append(values);}
  const actions=node('div','modal-actions');actions.append(paperAction('취소하고 다시 살펴보기',async()=>{const d=await act('cancel');if(d){if(c.kind==='control')openControl();else overlay.close();}},'cancel-review'),paperAction(c.kind==='abandon'?'탈출을 포기한다':'최종 확정',async()=>{const d=await act('confirm',{token:c.token});if(d&&d.game.status==='playing'&&!d.ui?.control)overlay.close();},c.kind==='abandon'?'abandon-final':'confirm-final','primary'));content.append(actions);body.append(content);
}
function openEnding() {
  if(!state?.news)return;const body=openOverlay(state.news.label,'ending','13-Fri · THE LAST RECORD');const paper=node('article','ending-paper');paper.append(node('div','news-masthead','열차 실종 사건'),node('span','eyebrow',state.status==='good'?'발견 속보 · 2026':'미제 사건 · 실종 10년'),node('h3','',state.news.headline));const image=node('img');image.src=state.status==='good'?'/assets/images/scene_04.png':'/assets/images/scene_01.png';image.alt=state.status==='good'?'열차가 정차한 승강장':'계속되는 열차의 밤';paper.append(image,node('p','',state.news.body));
  if(state.status==='good')paper.append(node('p','ending-cookie','아지산 — 생존. 길었던 밤을 지나, 살아 돌아오다.'));
  const actions=node('div','ending-actions');actions.append(button('처음부터 다시 조사하기',confirmNewGame,'brass-button'));body.append(paper,actions);
}
function openSettings() {
  const body=openOverlay('설정과 진행','settings','TRAVEL OPTIONS'),list=node('div','settings-list');
  if(window.TrainAudio){
    const toggle=node('label','audio-setting'),enabled=node('input');enabled.type='checkbox';enabled.checked=!window.TrainAudio.isMuted();
    enabled.addEventListener('change',()=>window.TrainAudio.setMuted(!enabled.checked));toggle.append(enabled,node('span','','배경음악 재생'));
    const volume=node('label','audio-setting'),slider=node('input'),value=node('output','',window.TrainAudio.getVolume()+'%');
    slider.type='range';slider.min='0';slider.max='100';slider.step='5';slider.value=String(window.TrainAudio.getVolume());slider.setAttribute('aria-label','배경음악 음량');
    slider.addEventListener('input',()=>{window.TrainAudio.setVolume(slider.value);value.value=slider.value+'%';});
    volume.append(node('span','','음악 음량'),slider,value);list.append(toggle,volume);
  }
  const l=node('label'),check=node('input');check.type='checkbox';check.checked=document.documentElement.classList.contains('reduced-motion');
  check.addEventListener('change',()=>{document.documentElement.classList.toggle('reduced-motion',check.checked);try{localStorage.setItem('train_reduced_motion',String(check.checked));}catch{}});
  l.append(check,node('span','','움직임 효과 줄이기'));
  list.append(l,node('p','','진행은 현재 브라우저에 연결된 기록으로 자동 보관됩니다. 잠시 쉬려면 창을 닫고 다시 이어서 조사할 수 있습니다.'),button('조사 기록 보기',openJournal),button('새로운 조사 시작',confirmNewGame));
  if(state?.status==='playing')list.append(button('탈출 포기 여부 선택',()=>act('abandon'),'',true));body.append(list);
}
function confirmNewGame() {if(busy)return;const body=openOverlay('새로운 조사 시작','newgame','NEW INVESTIGATION');const c=node('div','modal-content');c.append(node('p','','이 화면은 새 게임으로 시작합니다. 소지품과 진행이 처음 상태로 돌아갑니다. 새로 시작할까요?'));const actions=node('div','modal-actions');actions.append(button('이어서 조사하기',()=>overlay.close()),button('새 게임 시작',()=>startNewGame(),'primary'));c.append(actions);body.append(c);}
async function startNewGame() {if(busy)return;if(overlay.open)overlay.close();showSceneLoading(true);setBusy(true);clearError();try{const data=await request('/api/game/new',{username:state?.username||shell.dataset.username||'사용자'});controlDraft={destination:'',password:'0000'};documents.clear();seenEvents.clear();acquisitionQueue=[];dismissAcquisition();selectedDocument=null;lastRequest=null;state=null;await prepareScene(data,true);overlay.close();apply(data,true);}catch(e){setError(e.message,false);}finally{showSceneLoading(false);setBusy(false);}}
async function sendText(message) { if(overlay.open)overlay.close();$('user-message').value=message;return perform({message}); }
$('chat-form').addEventListener('submit',e=>{e.preventDefault();const message=$('user-message').value.trim();if(message)perform({message});});
$('user-message').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();$('chat-form').requestSubmit();}});
$('user-message').addEventListener('input',e=>{e.target.style.height='auto';e.target.style.height=Math.min(e.target.scrollHeight,100)+'px';});
$('close-dialogue').addEventListener('click',()=>{setDialogueVisible(false);(document.querySelector('.person-hotspot.talking')||$('hint-btn')).focus({preventScroll:true});});
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!e.isComposing&&!overlay.open&&!$('dialogue-box').hidden){e.preventDefault();setDialogueVisible(false);}});
$('menu-btn').addEventListener('click',openSettings);
$('hint-choice').addEventListener('click',()=>{if(activeHintChoice)perform({action:{...activeHintChoice.action}});});
$('bag-btn').addEventListener('click',()=>openInventory());$('end-talk').addEventListener('click',()=>act('end_talk'));$('history-btn').addEventListener('click',openHistory);$('hint-btn').addEventListener('click',()=>act('hint'));$('settings-btn').addEventListener('click',openSettings);$('close-overlay').addEventListener('click',closeOverlay);overlay.addEventListener('close',stopOverlayMedia);overlay.addEventListener('cancel',e=>{e.preventDefault();closeOverlay();});
$('retry-btn').addEventListener('click',()=>{if(lastRequest)perform(lastRequest,true);});$('reload-btn').addEventListener('click',async()=>{if(busy)return;try{const data=await request('/api/game');await prepareScene(data);apply(data);clearError();toast('진행 기록을 불러왔습니다.');}catch(e){setError(e.message,false);}finally{showSceneLoading(false);}});
$('scene-world').addEventListener('pointermove',e=>{if(scene?.light_mode!=='flashlight'||state?.npc)return;const r=e.currentTarget.getBoundingClientRect();$('darkness').style.setProperty('--beam-x',((e.clientX-r.left)/r.width*100)+'%');$('darkness').style.setProperty('--beam-y',((e.clientY-r.top)/r.height*100)+'%');});
try{if(localStorage.getItem('train_reduced_motion')==='true')document.documentElement.classList.add('reduced-motion');}catch{}
window.addEventListener('resize',fitConversation);
window.visualViewport?.addEventListener('resize',fitConversation);
if(window.ResizeObserver){
  const conversationObserver=new ResizeObserver(fitConversation);
  conversationObserver.observe(document.querySelector('.conversation-console'));
  conversationObserver.observe(document.querySelector('.train-map-bar'));
}
(async()=>{showSceneLoading(true);setBusy(true);try{const params=new URLSearchParams(location.search);let data;if(params.get('new')==='1'){data=await request('/api/game/new',{username:shell.dataset.username||'사용자'});params.delete('new');history.replaceState(null,'',location.pathname+(params.toString()?'?'+params:''));}else{try{data=await request('/api/game');}catch(e){if(e.code!=='game_missing')throw e;data=await request('/api/game/new',{username:shell.dataset.username||'사용자'});}}await prepareScene(data,true);apply(data,true);}catch(e){setError(e.message,false);$('save-status').textContent='불러오기 실패';}finally{showSceneLoading(false);setBusy(false);}})();

})();
