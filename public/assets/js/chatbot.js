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
let selectedDocument = null;
const documents = new Map();
const seenEvents = new Set();
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
  await Promise.all([prepareImage(data.scene.background),...data.scene.people.filter(p=>p.active||!data.game.npc).map(p=>prepareImage(p.image))]);

}
function acquisition(events) {
  for(const e of events) {const id=e.event_id||e.item.id;if(seenEvents.has(id))continue;seenEvents.add(id);acquisitionQueue.push(e.item);}
  showAcquisition();
}
function showAcquisition() {
  if(acquisitionActive||!acquisitionQueue.length)return;
  acquisitionActive=true;const item=acquisitionQueue.shift(),card=$('acquisition-notice');card.replaceChildren();
  const art=node('div','acquired-icon');art.append(icon(itemIcon(item.kind)));
  const copy=node('div','acquired-copy');copy.append(node('small','','소지품 획득'),node('strong','',item.name),node('span','','보관함에 보관되었습니다.'));
  const close=button('×',dismissAcquisition,'acquired-close');close.setAttribute('aria-label','획득 알림 닫기');
  card.append(art,copy,close);card.hidden=false;card.classList.add('appearing');placeAcquisition();
  clearTimeout(acquisitionTimer);acquisitionTimer=setTimeout(dismissAcquisition,4500);
}
function placeAcquisition(){const card=$('acquisition-notice');if(overlay.open){card.classList.add('in-focus');$('overlay-header-anchor')?.remove();overlay.insertBefore(card,$('overlay-body'));}else{card.classList.remove('in-focus');document.body.append(card);}}
overlay.addEventListener('close',placeAcquisition);
function dismissAcquisition(){clearTimeout(acquisitionTimer);$('acquisition-notice').hidden=true;acquisitionActive=false;showAcquisition();}

const itemIcon = (kind) => kind === 'flashlight' ? 'flashlight' : kind === 'manual' ? 'book' : 'ticket';
function node(tag, cls = '', text = '') { const n = document.createElement(tag); if (cls) n.className = cls; if (text) n.textContent = text; return n; }
function icon(name) { const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); const use = document.createElementNS('http://www.w3.org/2000/svg', 'use'); use.setAttribute('href', '#i-' + name); svg.append(use); svg.setAttribute('aria-hidden','true'); return svg; }
function button(text, handler, cls = '', server = false) { const b = node('button', cls, text); b.type = 'button'; if (server) { b.dataset.busyControl = '1'; b.disabled = busy; } b.addEventListener('click', handler); return b; }
function toast(text) { clearTimeout(toastTimer); $('toast').textContent = text; $('toast').hidden = false; toastTimer = setTimeout(() => { $('toast').hidden = true; }, 3800); }
function setBusy(value) { busy = value; $('send-btn').disabled = busy || state?.status !== 'playing'; $('user-message').disabled = busy || state?.status !== 'playing'; document.querySelectorAll('[data-busy-control]').forEach(b => { b.disabled = busy || b.dataset.locked === '1'; }); $('save-status').textContent = busy ? '응답을 기다리는 중' : '기록 보관됨'; }
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
  const body=reuse?content:{...content,request_id:crypto.randomUUID?crypto.randomUUID():'turn_'+Date.now()+'_'+Math.random().toString(36).slice(2),revision:state.revision};
  const likelyTravel=typeof body.message==='string'&&/^(?:[1-4]호차|다음\s*칸|이전\s*칸|승무원실|기관실)(?:로|으로)?\s*(?:이동|가겠|갑니다|간다|돌아|들어갑)/.test(body.message.trim())&&!/않|안\s*가|했|다면|[?]/.test(body.message);
  const expectedTransition=likelyTravel||body.action?.type==='move'||body.action?.type==='disembark'||(body.action?.type==='confirm'&&state.confirmation?.kind==='control');
  lastRequest=body;setBusy(true);if(expectedTransition){if(overlay.open)overlay.close();showSceneLoading(true);}
  try {
    const data=await request('/api/chat',body);await prepareScene(data);apply(data);lastRequest=null;
    if(body.action?.type==='present'&&overlay.open&&!data.ui?.inventory&&!data.ui?.document&&!data.game.confirmation)overlay.close();
    if(body.message){$('user-message').value='';$('user-message').style.height='auto';}
    if(data.ui?.ignored)$('reply-status').textContent='장면에 반영되지 않은 입력입니다.';
    return data;
  } catch(e) {setError(e.message,e.code!=='stale_state');if(e.code==='stale_state'){lastRequest=null;try{const data=await request('/api/game');await prepareScene(data);apply(data);}catch{}}return null;}
  finally{showSceneLoading(false);setBusy(false);}
}
const act=(type,extra={}) => perform({action:{type,...extra}});
function latest() { return state?.history?.slice(-1)[0]; }
function apply(data, force = false) {
  if(!data?.game || !data?.scene) throw new Error('진행 상태 응답이 올바르지 않습니다.');
  if(!force && state && data.game.revision < state.revision) return;
  state=data.game; scene=data.scene;
  $('location-name').textContent=state.location.name;
  $('time-display').textContent=scene.arrived?'23:59 · 정차':'23:59';
  const bg=$('scene-image');if(bg.getAttribute('src')!==scene.background)bg.src=scene.background;
  bg.alt=state.location.name+'의 현재 장면';
  $('darkness').hidden=scene.light_mode==='normal';$('darkness').classList.toggle('flashlight-mask',scene.light_mode==='flashlight');if(state.npc){$('darkness').style.setProperty('--beam-x','50%');$('darkness').style.setProperty('--beam-y','48%');}
  $('scene-world').dataset.mode=state.npc?'conversation':'exploration';
  $('scene-caption').textContent=scene.dark?'불이 꺼져 아무것도 보이지 않는다.':state.status!=='playing'?'끝나지 않던 밤의 기록.':'';
  const layer=$('character-layer');layer.replaceChildren();
  const people=state.npc?scene.people.filter(p=>p.active):scene.people;
  people.forEach(p=>{
    const b=button('',()=>act('select_npc',{target:p.id}),'person-hotspot'+(p.active?' talking':''),true);b.dataset.npc=p.id;
    b.setAttribute('aria-label',p.name+'에게 말 걸기');b.title=p.name+' · 대화 시작';
    const bounds=p.active?[31,3,38,97]:p.bounds;place(b,bounds);
    const img=node('img','character-sprite');img.src=p.image;img.alt=p.name;img.draggable=false;
    const label=node('span','hotspot-label',p.name+' · 대화');b.append(img,label);layer.append(b);
  });
  $('conversation-badge').hidden=!state.npc;$('active-person').textContent=state.npc?(scene.people.find(p=>p.id===state.npc)?.name||'인물')+'와 대화 중':'';
  $('interaction-guide').textContent=state.npc?'채팅으로 대화하세요. 대화를 마치려면 위의 ‘대화 마치기’를 누르세요.':'빛나는 지점에 커서를 올려 대상을 확인하세요. 채팅으로도 조사할 수 있습니다.';
  $('question-reference').hidden=!state.suggestions?.length;$('suggested-questions').textContent=(state.suggestions||[]).join(' / ');
  const entry=latest(); $('speaker-name').textContent=entry?.speaker || '차내'; $('dialogue-text').textContent=entry?.text || data.reply; $('dialogue-text').scrollTop=0;
  $('current-target').textContent=state.npc? (scene.people.find(p=>p.id===state.npc)?.name || '상대')+'에게 말하거나 주변에 행동하기':'현재 장면에 행동하기';
  $('item-count').textContent=state.inventory.length; $('bag-btn').classList.toggle('bag-pulse',!!state.bag_hint);
  $('objective').textContent=state.objective; $('mobile-objective').textContent=state.objective;
  $('journal-note').textContent=state.journal.at(-1) || '아직 확인한 단서가 없습니다.';
  const minis=$('mini-items');minis.replaceChildren();state.inventory.slice(-4).forEach(i=>{const m=node('span','mini-item');m.title=i.name;m.append(icon(itemIcon(i.kind)));minis.append(m);});
  renderLinearMap();renderSceneActions();
  acquisition((data.events||[]).filter(e=>e.type==='item_acquired'));
  if(state.status!=='playing') openEnding();
  else if(state.confirmation) openConfirmation();
  else if(data.ui?.document) { selectedDocument=data.ui.document;documents.set(selectedDocument.id,selectedDocument);openInventory(selectedDocument); }
  else if(data.ui?.notice) openNotice();
  else if(data.ui?.inventory) openInventory();
  else if(data.ui?.control) openControl();
  else if(overlay.open && overlay.dataset.view==='lever') openLever();
  setBusy(busy);
}
function place(el,bounds){const [x,y,w,h]=bounds;Object.assign(el.style,{left:x+'%',top:y+'%',width:w+'%',height:h+'%'});}
function renderLinearMap(){
  const box=$('train-map');box.replaceChildren();
  state.map.forEach((p,i)=>{const b=button('',async()=>{if(overlay.open)overlay.close();await act(p.id==='platform'?'disembark':'move',{target:p.id});},'linear-stop'+(p.current?' current':p.visited?' visited':''),true);
    b.dataset.location=p.id;b.setAttribute('aria-current',p.current?'location':'false');b.title=p.id==='crew'?'승무원실 · 4호차에서 연결':p.name;
    b.append(node('span','stop-index',p.id.startsWith('car_')?p.id.slice(-1):p.id==='crew'?'업무':p.id==='engine'?'운전':'하차'),node('span','stop-name',p.name));
    if(!p.open||p.current||state.status!=='playing'){b.disabled=true;b.dataset.locked='1';}box.append(b);
  });
  const active=box.querySelector('.current');if(active&&matchMedia('(max-width:700px)').matches)box.scrollLeft=active.offsetLeft-box.clientWidth/2+active.clientWidth/2;
}
function renderSceneActions(){
 const layer=$('scene-hotspots');layer.replaceChildren();
 if(state.status!=='playing')return;
 (scene.hotspots||[]).forEach(p=>{const b=button('',()=>{
   if(p.kind==='focus'){if(p.target==='door')openLever();else if(p.target==='control'){if(state.controls.control)openControl();else if(state.controls.proof)openInventory();else toast('먼저 기관사에게 장치에 관해 물어보세요.');}}
   else act(p.kind,{target:p.target});
 },'world-hotspot '+(p.appearance||''),true);b.dataset.hotspot=p.id;b.setAttribute('aria-label',p.label);b.title=p.label;place(b,p.bounds);
 const outline=document.createElementNS('http://www.w3.org/2000/svg','svg');outline.setAttribute('viewBox','0 0 100 100');outline.setAttribute('preserveAspectRatio','none');outline.setAttribute('aria-hidden','true');const rect=document.createElementNS('http://www.w3.org/2000/svg','rect');for(const [k,v] of Object.entries({x:2,y:2,width:96,height:96,rx:4}))rect.setAttribute(k,String(v));outline.append(rect);
 b.append(outline,node('span','hotspot-dot',''),node('span','hotspot-label',p.label));
 if(p.appearance==='paper')b.append(node('span','notice-mark','안내문'));layer.append(b);
 });
}
function openNotice(){const body=openOverlay('기관실 안내문','notice','ONBOARD NOTICE');const page=node('article','notice-focus');page.append(node('span','eyebrow','WARNING'),node('h3','','열차의 정차는\n기관실에서만 가능'),node('p','','안내문을 직접 읽고 조사 기록에 남겼습니다.'));body.append(page);}
function openOverlay(title, view, eyebrow='13-Fri · INVESTIGATION') { overlay.dataset.view=view; $('overlay-title').textContent=title; $('overlay-eyebrow').textContent=eyebrow; $('overlay-body').replaceChildren(); if(!overlay.open) overlay.showModal();placeAcquisition(); return $('overlay-body'); }
function closeOverlay() { if(busy && overlay.dataset.view==='confirm') return; if(overlay.dataset.view==='confirm' && state?.confirmation) { act('cancel').then(data=>{if(data) overlay.close();}); } else overlay.close(); }
function openInventory(doc = null) {
  if(!state) return;
  const body=openOverlay('보관함','inventory','INVENTORY · 모은 물건과 조사 기록');
  const book=node('div','book-layout'),list=node('nav','item-list'),page=node('article','book-page'); list.setAttribute('aria-label','소지품 목록');
  const selected=doc && state.inventory.some(i=>i.id===doc.id)?doc:null;
  state.inventory.forEach(i=>{const b=button('',()=>openItem(i.id),'item-row'+(selected?.id===i.id?' selected':''),true);b.append(icon(itemIcon(i.kind)));const info=node('span','',i.name);info.append(node('small','',i.read?'확인한 물건':'열어서 확인'));b.append(info);list.append(b);});
  if(selected) renderDocument(page,selected);
  else { const e=node('div','empty-page'); e.append(icon('bag'),node('h3','','무엇을 살펴볼까요?'),node('p','','가진 물건을 골라 직접 확인하세요.'));page.append(e); }
  book.append(list,page);body.append(book);
}
async function openItem(id) {
  if(busy) return;
  if(state.status!=='playing') { try { const data=await request('/api/item/'+encodeURIComponent(id));openInventory(data.document); }catch(e){setError(e.message,false);} return; }
  await act('read_item',{target:id});
}
function renderDocument(page,doc) {
  page.append(node('span','eyebrow',doc.eyebrow||'INVESTIGATION RECORD'));
  if(doc.kind==='ticket'||doc.kind==='ticket-old') {const t=node('div','ticket-illustration'+(doc.kind==='ticket-old'?' old-ticket':''));t.append(node('span','','PASSENGER TICKET'),node('strong','','13-Fri'),node('span','',doc.fields?.find(f=>f[0]==='발급 연도')?.[1]||''));page.append(t);}
  page.append(node('h3','',doc.title));
  if(doc.id==='facility_manual'){const diagram=node('div','manual-diagram');diagram.append(node('div','manual-door'));const hatch=node('div','manual-hatch');hatch.append(node('i','manual-lever'),node('span','','↓'));diagram.append(hatch,node('span','manual-caption','오른쪽 하단 점검 덮개 · 노란 레버를 아래로'));page.append(diagram);}

  if(doc.image){const frame=node('figure','archive-photo');const img=node('img','document-photo');img.src=doc.image;img.alt='13-Fri 열차의 과거 자료 사진';frame.append(img,node('span','archive-tag','13-Fri'));page.append(frame);}
  if(doc.fields?.length){const grid=node('div','document-fields');doc.fields.forEach(([k,v])=>{const f=node('div','document-field');f.append(node('b','',k),node('span','',v));grid.append(f);});page.append(grid);}
  (doc.paragraphs||[]).forEach(t=>page.append(node('p','',t)));
  if(doc.kind==='report')page.append(node('span','document-stamp','RAILWAY RECORD'));
  const actions=node('div','document-actions');
  if(state.status==='playing') {
    if(doc.id==='flashlight')actions.append(button('손전등 사용',()=>act('use_item',{target:doc.id}),'',true));
    if(doc.id==='ticket_old' && state.location.id==='car_3') actions.append(button(state.inventory.find(i=>i.id==='ticket_old')?.name.includes('조사 기록')?'노인에게 조사 기록 보여주기':'노인에게 원본 돌려드리기',()=>act('present',{target:'ticket_old',recipient:'elder'}),'',true));
    if(doc.id==='route_report' && state.location.id==='car_4')actions.append(button('승무원에게 보고서 보여주기',()=>act('present',{target:'route_report',recipient:'attendant'}),'',true));
    if(state.controls.proof)actions.append(button('이 물건을 최종 증거로 제출',()=>act('prepare_evidence',{target:doc.id}),'danger-action',true));
  }
  if(actions.childElementCount)page.append(actions);
}
function openMap() {
  if(!state)return;const body=openOverlay('열차 안내도','map','TRAIN MAP · 현재 위치와 연결');const sheet=node('div','map-sheet');sheet.append(node('p','','방문한 장소로 돌아가 놓친 기록을 확인할 수 있습니다. 잠긴 구역은 조건을 충족해야 진입할 수 있습니다.'));
  const grid=node('div','map-nodes');state.map.forEach(p=>{const b=button(p.name,async()=>{const d=await act('move',{target:p.id});if(d&&d.game.location.id===p.id)overlay.close();},'map-node'+(p.current?' current':''),true);if(!p.open||state.status!=='playing'){b.disabled=true;b.dataset.locked='1';}b.append(node('span','',p.current?'현재 위치':p.open?(p.visited?'방문한 장소':'이동 가능'):'아직 진입할 수 없음'));grid.append(b);});sheet.append(grid,node('p','map-foot','1호차 ↔ 2호차 ↔ 3호차 ↔ 4호차 / 4호차에서 승무원실과 기관실로 연결'));body.append(sheet);
}
function openHistory() { if(!state)return;const body=openOverlay('대화 기록','history','CONVERSATION · 실제로 오간 이야기');const list=node('div','history-list');state.history.forEach(h=>{const r=node('article','history-row '+h.role);r.append(node('strong','',h.speaker),node('p','',h.text));if(h.record){const d=node('details');d.append(node('summary','','대화에서 확인한 사실'),node('p','',h.record));r.append(d);}list.append(r);});body.append(list);list.scrollTop=list.scrollHeight; }
function openJournal() {if(!state)return;const body=openOverlay('조사 기록','journal','FIELD NOTES · 확인한 사실');const list=node('div','journal-list');(state.journal.length?state.journal:['아직 확인한 단서가 없습니다.']).forEach(t=>list.append(node('p','journal-entry',t)));body.append(list);}
function openLever() {
  if(!state||state.location.id!=='car_4')return;const body=openOverlay('승무원실 출입문','lever','EMERGENCY ACCESS · 수동 조작');const wrap=node('div','lever-puzzle'),door=node('div','door-illustration'),copy=node('div','lever-copy');
  door.append(node('div','restricted-sign','관계자 외 출입금지'),node('div','card-reader'));
  const handle=button('',()=>act('operate',{target:'handle'}),'door-handle',true);handle.setAttribute('aria-label','문손잡이 당기기');door.append(handle);
  const cover=node('div','inspection-cover'+(state.door.cover_open?' cover-open':''));
  if(state.door.cover_open){cover.append(node('div','lever-track'));const grip=button('',()=>{},'lever-grip'+(state.door.lever_down?' down':''));grip.setAttribute('aria-label','노란색 레버. 아래로 드래그하거나 아래쪽 화살표를 누르세요.');grip.title='아래로 드래그';let startY=null;
    grip.addEventListener('pointerdown',e=>{if(busy)return;startY=e.clientY;grip.setPointerCapture(e.pointerId);e.preventDefault();});
    grip.addEventListener('pointerup',e=>{if(startY!==null){const dy=e.clientY-startY;startY=null;if(dy>35)act('operate',{target:'lever_down'});}});
    grip.addEventListener('pointercancel',()=>{startY=null;});grip.addEventListener('keydown',e=>{if(['ArrowDown','Enter',' '].includes(e.key)){e.preventDefault();act('operate',{target:'lever_down'});}});cover.append(grip);
  }else {const hatch=button('점검 덮개',()=>act('operate',{target:'cover'}),'cover-button',true);hatch.setAttribute('aria-label','점검 덮개 열기');cover.append(hatch);}
  door.append(cover);copy.append(node('span','eyebrow',state.door.open?'DOOR OPEN':'MANUAL RELEASE'),node('p','',state.door.open?'잠금이 풀려 문이 열렸다. 안쪽으로 들어갈 수 있다.':state.door.lever_down?'철컥, 잠금 해제음이 들렸다. 이제 문손잡이를 당겨 문을 열 수 있다.':state.door.cover_open?'점검 덮개가 열렸다. 안쪽의 노란색 수동 해제 레버가 보인다. 안내서에서 확인한 방향으로 조작할 수 있다.':'카드 인식기에 빨간불이 깜빡인다. 손잡이를 당겨도 문이 움직이지 않는다. 보관함의 시설 안내서를 참고할 수 있다.'));
  
  if(state.door.cover_open&&!state.door.lever_down&&!state.door.open){copy.append(button('레버를 아래로 끝까지 내리기',()=>act('operate',{target:'lever_down'}),'',true));copy.append(node('p','lever-keyboard','화면의 노란 레버를 아래로 드래그해도 같은 조작이 됩니다. 키보드와 채팅 입력도 가능합니다.'));}
  
  if(state.door.open)copy.append(button('승무원실로 들어가기',async()=>{const d=await act('move',{target:'crew'});if(d?.game.location.id==='crew')overlay.close();},'',true));
  copy.append(button('보관함 열기',()=>openInventory()));wrap.append(door,copy);body.append(wrap);
}
function openControl() {
  if(!state?.controls.control)return;const body=openOverlay('분기기 제어 장치','control','CONTROL PANEL · 마지막 입력');const form=node('form','control-panel'),heading=node('div','control-heading');heading.append(node('span','eyebrow','ROUTE CONTROL'),node('span','remaining','남은 기회 '+state.attempts+'회'));form.append(heading);
  const label=node('label','','목적지');label.htmlFor='destination-input';const destination=node('input','destination-input');destination.id='destination-input';destination.name='destination';destination.required=true;destination.maxLength=30;destination.placeholder='조사한 목적지를 직접 입력하세요';destination.autocomplete='off';form.append(label,destination,node('label','','네 자리 비밀번호'));
  const row=node('div','digit-wheel-row');const inputs=[];
  for(let i=0;i<4;i++){const wheel=node('div','digit-wheel');const input=node('input');input.type='text';input.inputMode='numeric';input.maxLength=1;input.pattern='[0-9]';input.required=true;input.setAttribute('aria-label','비밀번호 '+(i+1)+'번째 숫자');input.autocomplete='off';
    const spin=(d)=>{input.value=String(((parseInt(input.value||'0',10)||0)+d+10)%10);};wheel.append(button('▲',()=>spin(1)),input,button('▼',()=>spin(-1)));row.append(wheel);inputs.push(input);
    input.addEventListener('input',()=>{input.value=input.value.replace(/[^0-9]/g,'').slice(-1);if(input.value&&i<3)inputs[i+1].focus();});input.addEventListener('keydown',e=>{if(e.key==='Backspace'&&!input.value&&i>0)inputs[i-1].focus();});input.addEventListener('paste',e=>{const digits=e.clipboardData.getData('text').trim();if(/^[0-9]{4}$/.test(digits)){e.preventDefault();digits.split('').forEach((v,j)=>inputs[j].value=v);inputs[3].focus();}});
  }
  form.append(row);const submit=node('button','brass-button','입력 내용을 확인하고 최종 제출 준비');submit.type='submit';submit.dataset.busyControl='1';form.append(submit,node('p','control-note','확인 화면에서 확정하기 전에는 기회가 소모되지 않습니다. 목적지와 비밀번호를 신중하게 확인하세요.'));
  form.addEventListener('submit',e=>{e.preventDefault();if(form.reportValidity())act('prepare_control',{destination:destination.value,password:inputs.map(i=>i.value).join('')});});body.append(form);
}
function openConfirmation() {
  const c=state?.confirmation;if(!c)return;const body=openOverlay(c.title,'confirm','FINAL CONFIRMATION · 되돌릴 수 없는 선택');const content=node('div','modal-content');content.append(node('p','',c.text));
  if(c.kind==='control'){const values=node('div','confirmation-values');values.append(node('span','','목적지: '+c.destination),node('span','','비밀번호: '+c.password));content.append(values);}
  if(c.kind==='evidence'){const values=node('div','confirmation-values',c.title);content.append(values);}
  const actions=node('div','modal-actions');actions.append(button('취소하고 다시 살펴보기',async()=>{const d=await act('cancel');if(d)overlay.close();},'',true),button(c.kind==='abandon'?'탈출을 포기한다':'최종 확정',async()=>{const d=await act('confirm',{token:c.token});if(d&&d.game.status==='playing'&&!d.ui?.control)overlay.close();},'primary',true));content.append(actions);body.append(content);
}
function openEnding() {
  if(!state?.news)return;const body=openOverlay(state.news.label,'ending','13-Fri · THE LAST RECORD');const paper=node('article','ending-paper');paper.append(node('div','news-masthead','열차 실종 사건'),node('span','eyebrow',state.status==='good'?'발견 속보 · 2026':'미제 사건 · 실종 10년'),node('h3','',state.news.headline));const image=node('img');image.src=state.status==='good'?'/assets/images/scene_04.png':'/assets/images/scene_01.png';image.alt=state.status==='good'?'열차가 정차한 승강장':'계속되는 열차의 밤';paper.append(image,node('p','',state.news.body));
  if(state.status==='good')paper.append(node('p','ending-cookie','아지산 — 생존. 길었던 밤을 지나, 살아 돌아오다.'));
  const actions=node('div','ending-actions');actions.append(button('처음부터 다시 조사하기',confirmNewGame,'brass-button'));body.append(paper,actions);
}
function openSettings() {const body=openOverlay('설정과 진행','settings','TRAVEL OPTIONS');const list=node('div','settings-list');const l=node('label');const check=node('input');check.type='checkbox';check.checked=document.documentElement.classList.contains('reduced-motion');check.addEventListener('change',()=>{document.documentElement.classList.toggle('reduced-motion',check.checked);try{localStorage.setItem('train_reduced_motion',String(check.checked));}catch{}});l.append(check,node('span','','움직임 효과 줄이기'));list.append(l,node('p','','진행은 현재 브라우저에 연결된 기록으로 자동 보관됩니다. 잠시 쉬려면 창을 닫고 다시 이어서 조사할 수 있습니다.'),button('새로운 조사 시작',confirmNewGame));if(state?.status==='playing')list.append(button('탈출 포기 여부 선택',()=>act('abandon'),'',true));body.append(list);}
function confirmNewGame() {if(busy)return;const body=openOverlay('새로운 조사 시작','newgame','NEW INVESTIGATION');const c=node('div','modal-content');c.append(node('p','','이 화면은 새 게임으로 시작합니다. 소지품과 진행이 처음 상태로 돌아갑니다. 새로 시작할까요?'));const actions=node('div','modal-actions');actions.append(button('이어서 조사하기',()=>overlay.close()),button('새 게임 시작',()=>startNewGame(),'primary'));c.append(actions);body.append(c);}
async function startNewGame() {if(busy)return;if(overlay.open)overlay.close();showSceneLoading(true);setBusy(true);clearError();try{const data=await request('/api/game/new',{username:state?.username||shell.dataset.username||'사용자'});documents.clear();seenEvents.clear();acquisitionQueue=[];dismissAcquisition();selectedDocument=null;lastRequest=null;state=null;await prepareScene(data,true);overlay.close();apply(data,true);}catch(e){setError(e.message,false);}finally{showSceneLoading(false);setBusy(false);}}
async function sendText(message) { if(overlay.open)overlay.close();$('user-message').value=message;return perform({message}); }
$('chat-form').addEventListener('submit',e=>{e.preventDefault();const message=$('user-message').value.trim();if(message)perform({message});});
$('user-message').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();$('chat-form').requestSubmit();}});
$('user-message').addEventListener('input',e=>{e.target.style.height='auto';e.target.style.height=Math.min(e.target.scrollHeight,100)+'px';});
$('bag-btn').addEventListener('click',()=>openInventory());$('inventory-preview').addEventListener('click',()=>openInventory());$('end-talk').addEventListener('click',()=>act('end_talk'));$('journal-preview').addEventListener('click',openJournal);$('history-btn').addEventListener('click',openHistory);$('hint-btn').addEventListener('click',()=>act('hint'));$('settings-btn').addEventListener('click',openSettings);$('close-overlay').addEventListener('click',closeOverlay);overlay.addEventListener('cancel',e=>{e.preventDefault();closeOverlay();});
$('retry-btn').addEventListener('click',()=>{if(lastRequest)perform(lastRequest,true);});$('reload-btn').addEventListener('click',async()=>{if(busy)return;try{const data=await request('/api/game');await prepareScene(data);apply(data);clearError();toast('진행 기록을 불러왔습니다.');}catch(e){setError(e.message,false);}finally{showSceneLoading(false);}});
let clockStartedAt=null;
setInterval(()=>{if(!state?.clock_running){clockStartedAt=null;return;}if(clockStartedAt===null)clockStartedAt=Date.now();const elapsed=Math.floor((Date.now()-clockStartedAt)/1000);const t=(23*3600+59*60+elapsed)%86400;$('time-display').textContent=[Math.floor(t/3600),Math.floor(t%3600/60),t%60].map(x=>String(x).padStart(2,'0')).join(':')+' · 정차';},1000);
$('scene-world').addEventListener('pointermove',e=>{if(scene?.light_mode!=='flashlight'||state?.npc)return;const r=e.currentTarget.getBoundingClientRect();$('darkness').style.setProperty('--beam-x',((e.clientX-r.left)/r.width*100)+'%');$('darkness').style.setProperty('--beam-y',((e.clientY-r.top)/r.height*100)+'%');});
try{if(localStorage.getItem('train_reduced_motion')==='true')document.documentElement.classList.add('reduced-motion');}catch{}
(async()=>{showSceneLoading(true);setBusy(true);try{const params=new URLSearchParams(location.search);let data;if(params.get('new')==='1'){data=await request('/api/game/new',{username:shell.dataset.username||'사용자'});params.delete('new');history.replaceState(null,'',location.pathname+(params.toString()?'?'+params:''));}else{try{data=await request('/api/game');}catch(e){if(e.code!=='game_missing')throw e;data=await request('/api/game/new',{username:shell.dataset.username||'사용자'});}}await prepareScene(data,true);apply(data,true);}catch(e){setError(e.message,false);$('save-status').textContent='불러오기 실패';}finally{showSceneLoading(false);setBusy(false);}})();

})();
