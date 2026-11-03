/* Adapted from the supplied lever-box.zip and dial-puzzle.zip.
 * Art coordinates and dial mechanics are retained; game outcomes come from the server.
 */
(() => {
  'use strict';
  const base = '/assets/puzzles/';
  let audio;
  function tick(freq = 1800, duration = .03, volume = .06) {
    try {
      audio ||= new (window.AudioContext || window.webkitAudioContext)();
      if (audio.state === 'suspended') audio.resume().catch(() => {});
      const start = audio.currentTime, oscillator = audio.createOscillator(), gain = audio.createGain();
      oscillator.type = 'square';
      oscillator.frequency.setValueAtTime(freq, start);
      oscillator.frequency.exponentialRampToValueAtTime(freq / 3, start + duration);
      gain.gain.setValueAtTime(volume, start);
      gain.gain.exponentialRampToValueAtTime(.0001, start + duration);
      oscillator.connect(gain).connect(audio.destination);
      oscillator.start(start); oscillator.stop(start + duration);
    } catch { /* Audio is optional. */ }
  }
  function mount(host, name, markup) {
    const root = host.attachShadow({mode: 'open'});
    const css = document.createElement('link');
    css.rel = 'stylesheet'; css.href = base + name + '/style.css';
    root.append(css);
    const stage = document.createElement('section');
    stage.className = 'stage'; stage.innerHTML = markup;
    root.append(stage);
    const image = stage.querySelector('img');
    image.addEventListener('error', () => {
      stage.querySelector('.status').textContent = '장치 이미지를 불러오지 못했습니다. 창을 닫고 다시 열어 주세요.';
    });
    return root;
  }
  function bindPull(button, pull) {
    let start = null, dragged = false;
    button.addEventListener('pointerdown', e => {
      if (button.disabled || e.button !== 0) return;
      start = e.clientY; dragged = false; button.setPointerCapture(e.pointerId);
    });
    button.addEventListener('pointerup', e => {
      if (start !== null && e.clientY - start > 25) { dragged = true; pull(); }
      start = null;
    });
    button.addEventListener('pointercancel', () => { start = null; dragged = false; });
    button.addEventListener('click', () => { if (!dragged) pull(); dragged = false; });
    button.addEventListener('keydown', e => {
      if (e.key === 'ArrowDown') { e.preventDefault(); pull(); }
    });
  }
  function mountLever(host, options) {
    const root = mount(host, 'lever-box', `
      <div class="box" id="box">
        <img class="box__bg" src="${base}lever-box/images/box.webp" width="1188" height="798" draggable="false" alt="열린 금속 점검함과 노란 수동 해제 레버">
        <button class="lever" type="button" aria-label="노란 레버 내리기" aria-pressed="false"><img class="lever__handle" src="${base}lever-box/images/lever-handle.webp" width="52" height="221" draggable="false" alt=""></button>
        <div class="cover-shade"><button class="cover-button" type="button">점검 덮개 열기</button></div>
      </div>
      <p class="status" role="status" aria-live="polite"></p>
      <div class="puzzle-actions"><button class="door-handle" type="button">문손잡이 당기기</button><button class="enter-room" type="button">승무원실로 들어가기</button><button class="inventory" type="button">보관함 열기</button></div>`);
    const box = root.querySelector('.box'), lever = root.querySelector('.lever');
    const cover = root.querySelector('.cover-button'), handle = root.querySelector('.door-handle');
    const enter = root.querySelector('.enter-room'), inventory = root.querySelector('.inventory');
    let door = options.door, waiting = false, externalBusy = false;
    function render() {
      box.classList.toggle('cover-closed', !door.cover_open);
      lever.classList.toggle('is-down', !!door.lever_down);
      lever.setAttribute('aria-pressed', String(!!door.lever_down));
      lever.disabled = waiting || externalBusy || !door.cover_open || door.lever_down || door.open;
      cover.disabled = handle.disabled = enter.disabled = inventory.disabled = waiting || externalBusy;
      handle.hidden = !!door.open;
      enter.hidden = !(door.open || door.lever_down);
      root.querySelector('.status').textContent = door.open ? '승무원실 문이 열렸다. 안쪽으로 들어갈 수 있다.'
        : door.lever_down ? '철컥― 잠금이 풀렸다. 승무원실로 들어갈 수 있다.'
        : door.cover_open ? '점검함 안에 노란 레버가 보인다.'
        : '출입문 옆 점검함이다. 덮개가 닫혀 있다.';
    }
    async function operate(target) {
      if (waiting || externalBusy) return;
      waiting = true;
      if (target === 'lever_down') { lever.classList.add('is-down'); tick(160, .2, .12); }
      for (const button of root.querySelectorAll('button')) button.disabled = true;
      try { await options.onOperate(target); }
      finally { waiting = false; if (host.isConnected) render(); }
    }
    cover.addEventListener('click', () => operate('cover'));
    bindPull(lever, () => { if (!lever.disabled) operate('lever_down'); });
    handle.addEventListener('click', () => operate('handle'));
    enter.addEventListener('click', options.onEnter);
    inventory.addEventListener('click', options.onInventory);
    const controller = {
      update(value) { door = value; render(); },
      setBusy(value) { externalBusy = value; if (!waiting) render(); },
    };
    render(); host.puzzle = controller; return controller;
  }
  const mod = (n, m) => ((n % m) + m) % m;
  const digitAt = angle => mod(Math.round(-angle / 36), 10);
  function mountDial(host, options) {
    const root = mount(host, 'dial-puzzle', `
      <div class="panel">
        <img class="panel__bg" src="${base}dial-puzzle/images/panel.webp" width="1402" height="1122" draggable="false" alt="도착역 표시창, 네 개의 숫자 다이얼과 확인 레버가 있는 놋쇠 패널">
        <div class="display"><label class="sr-only" for="station">도착역</label><input class="station" id="station" type="text" maxlength="30" placeholder="도착역을 적으세요" autocomplete="off" spellcheck="false"></div>
        <div class="dials" role="group" aria-label="비밀번호 다이얼 네 개"></div>
        <button class="lever" type="button" aria-label="레버 당기기 · 입력 내용 확인"><img class="lever__arm" src="${base}dial-puzzle/images/lever-arm.webp" width="170" height="399" draggable="false" alt=""></button>
      </div>
      <p class="status" role="status" aria-live="polite"></p>
      <p class="help">도착역을 적고 다이얼의 숫자를 위쪽 삼각 표시에 맞춘 뒤 레버를 당기세요. 드래그·클릭·휠·방향키·숫자키로 돌릴 수 있습니다.</p>
      <p class="help">최종 확인에서 확정할 때만 남은 기회가 사용됩니다.</p>`);
    const panel = root.querySelector('.panel'), station = root.querySelector('.station');
    const lever = root.querySelector('.lever'), status = root.querySelector('.status');
    const values = options.draft.password.split('').map(Number), ring = values.map(digit => -digit * 36), dials = [];
    let waiting = false, externalBusy = false;
    station.value = options.draft.destination;
    status.textContent = '남은 기회 ' + options.attempts + '회';
    const blocked = () => waiting || externalBusy;
    function changed() {
      options.onChange({destination: station.value, password: values.join('')});
      if (!blocked()) status.textContent = '남은 기회 ' + options.attempts + '회';
    }
    function render(i) {
      dials[i].style.setProperty('--ring', ring[i] + 'deg');
      dials[i].setAttribute('aria-valuenow', String(values[i]));
      dials[i].querySelectorAll('.dial__digit').forEach((digit, d) => digit.classList.toggle('is-on', d === values[i]));
    }
    function step(i, amount) {
      if (blocked()) return;
      ring[i] = Math.round(ring[i] / 36) * 36 - amount * 36;
      values[i] = digitAt(ring[i]); render(i); tick(); changed();
    }
    function setDigit(i, digit) {
      let diff = mod(digit - values[i], 10);
      if (diff > 5) diff -= 10;
      if (diff) step(i, diff);
    }
    [382.5, 590, 797.5, 1005].forEach((x, i) => {
      const dial = document.createElement('div'); dial.className = 'dial'; dial.tabIndex = 0;
      dial.setAttribute('role', 'spinbutton'); dial.setAttribute('aria-valuemin', '0'); dial.setAttribute('aria-valuemax', '9');
      dial.setAttribute('aria-label', '비밀번호 ' + (i + 1) + '번째 숫자');
      dial.style.left = x / 1402 * 100 + '%'; dial.style.top = 645 / 1122 * 100 + '%';
      dial.style.setProperty('--kx', x); dial.style.setProperty('--ky', 644);
      dial.innerHTML = '<span class="dial__knob"></span>' + Array.from({length: 10}, (_, digit) => `<span class="dial__digit" style="--i:${digit}" aria-hidden="true">${digit}</span>`).join('');
      root.querySelector('.dials').append(dial); dials.push(dial); render(i);
      dial.addEventListener('wheel', e => { e.preventDefault(); if (e.deltaY) step(i, e.deltaY > 0 ? 1 : -1); }, {passive: false});
      dial.addEventListener('keydown', e => {
        if (blocked() || e.isComposing) return;
        if (e.key === 'ArrowUp' || e.key === 'ArrowDown') { e.preventDefault(); step(i, e.key === 'ArrowUp' ? 1 : -1); }
        else if (e.key === 'ArrowRight') { e.preventDefault(); dials[Math.min(i + 1, 3)].focus(); }
        else if (e.key === 'ArrowLeft') { e.preventDefault(); (i ? dials[i - 1] : station).focus(); }
        else if (e.key === 'Enter') { e.preventDefault(); pull(); }
        else if (/^[0-9]$/.test(e.key)) { e.preventDefault(); setDigit(i, Number(e.key)); dials[Math.min(i + 1, 3)].focus(); }
        else if (e.key === ' ' ) { e.preventDefault(); step(i, 1); }
      });
      // A normal click advances one digit; dragging follows the pointer angle.
      let dragging = false, lastAngle = 0, moved = 0, suppressClick = false;
      const angleOf = e => { const r = dial.getBoundingClientRect(); return Math.atan2(e.clientY - r.top - r.height / 2, e.clientX - r.left - r.width / 2) * 180 / Math.PI; };
      dial.addEventListener('pointerdown', e => {
        if (blocked() || e.button !== 0) return;
        dragging = true; moved = 0; suppressClick = false;
        dial.setPointerCapture(e.pointerId); dial.classList.add('is-dragging'); lastAngle = angleOf(e);
      });
      dial.addEventListener('pointermove', e => {
        if (!dragging || blocked()) return;
        const angle = angleOf(e), delta = mod(angle - lastAngle + 180, 360) - 180;
        lastAngle = angle; moved += Math.abs(delta); ring[i] += delta;
        const digit = digitAt(ring[i]);
        if (values[i] !== digit) { values[i] = digit; tick(); changed(); }
        render(i);
      });
      function end(cancelled) {
        if (!dragging) return;
        dragging = false; dial.classList.remove('is-dragging');
        ring[i] = Math.round(ring[i] / 36) * 36;
        values[i] = digitAt(ring[i]); render(i); changed();
        suppressClick = cancelled || moved >= 4;
      }
      dial.addEventListener('pointerup', () => end(false));
      dial.addEventListener('pointercancel', () => end(true));
      dial.addEventListener('lostpointercapture', () => { if (dragging) end(true); });
      dial.addEventListener('click', () => { if (!suppressClick) step(i, 1); suppressClick = false; });
    });
    function updateBusy() {
      lever.disabled = blocked(); station.disabled = blocked();
      panel.classList.toggle('is-busy', blocked());
      dials.forEach(dial => { dial.setAttribute('aria-disabled', String(blocked())); dial.tabIndex = blocked() ? -1 : 0; });
    }
    async function pull() {
      if (blocked()) return;
      if (!station.value.trim()) { status.textContent = '도착역을 먼저 적어 주세요.'; station.focus(); return; }
      changed(); waiting = true; updateBusy();
      lever.classList.add('is-down'); tick(220, .18, .12);
      status.textContent = '입력 내용을 확인하고 있다…';
      try { await options.onSubmit({destination: station.value.trim(), password: values.join('')}); }
      finally { waiting = false; if (host.isConnected) { lever.classList.remove('is-down'); updateBusy(); } }
    }
    station.addEventListener('input', changed);
    station.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.isComposing) { e.preventDefault(); pull(); } });
    bindPull(lever, pull);
    host.puzzle = {setBusy(value) { externalBusy = value; updateBusy(); }};
    updateBusy(); return host.puzzle;
  }
  window.TrainPuzzles = Object.freeze({mountLever, mountDial});
})();
