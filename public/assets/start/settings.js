// 환경 설정: 창 열고 닫기 + 값 저장/불러오기
(function () {
  const KEY = 'noTerminus.settings';
  const DEFAULTS = { bgm: 70, sfx: 60, speed: 'normal', effects: true };

  function load() {
    try { return Object.assign({}, DEFAULTS, JSON.parse(localStorage.getItem(KEY) || '{}')); }
    catch (e) { return Object.assign({}, DEFAULTS); }
  }
  function save() {
    try { localStorage.setItem(KEY, JSON.stringify(settings)); } catch (e) { /* 저장 불가 환경 무시 */ }
  }

  let settings = load();

  // 다른 스크립트(타자 효과 등)에서 읽을 수 있게 공개
  window.gameSettings = {
    get: function (key) { return settings[key]; },
    // 글자 속도 → 타자 지연 배수
    speedMultiplier: function () { return { slow: 1.6, normal: 1, fast: 0.5 }[settings.speed] || 1; }
  };

  const dialog = document.getElementById('settingsDialog');
  const openBtn = document.getElementById('settingsBtn');
  const bgm = document.getElementById('setBgm');
  const sfx = document.getElementById('setSfx');
  const bgmOut = document.getElementById('bgmOut');
  const sfxOut = document.getElementById('sfxOut');
  const fx = document.getElementById('setFx');
  const segs = dialog.querySelectorAll('.seg');
  const resetBtn = document.getElementById('resetSettings');

  // 설정값 → 화면 반영
  function apply() {
    bgm.value = settings.bgm; bgmOut.textContent = settings.bgm;
    sfx.value = settings.sfx; sfxOut.textContent = settings.sfx;
    fx.checked = settings.effects;
    segs.forEach(function (b) { b.setAttribute('aria-pressed', String(b.dataset.speed === settings.speed)); });
    document.documentElement.classList.toggle('no-fx', !settings.effects);
    window.TrainAudio?.setVolume(settings.bgm);
  }

  openBtn.addEventListener('click', function () { settings.bgm = window.TrainAudio?.getVolume() ?? settings.bgm; apply(); dialog.showModal(); });

  // 바깥(어두운 배경) 클릭 시 닫기
  dialog.addEventListener('click', function (e) { if (e.target === dialog) dialog.close(); });

  bgm.addEventListener('input', function () { settings.bgm = Number(bgm.value); apply(); save(); });
  sfx.addEventListener('input', function () { settings.sfx = Number(sfx.value); apply(); save(); });
  fx.addEventListener('change', function () { settings.effects = fx.checked; apply(); save(); });
  segs.forEach(function (b) {
    b.addEventListener('click', function () { settings.speed = b.dataset.speed; apply(); save(); });
  });
  resetBtn.addEventListener('click', function () { settings = Object.assign({}, DEFAULTS); apply(); save(); });

  apply();
})();
