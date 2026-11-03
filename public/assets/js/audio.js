/* One shared, local music track for the title, boarding and game screens. */
(() => {
  'use strict';
  const settingsKey = 'noTerminus.settings';
  const positionKey = 'train.bgm.position';
  const muteKey = 'train.bgm.muted';
  const read = (storage, key, fallback) => { try { return JSON.parse(storage.getItem(key) || 'null') ?? fallback; } catch { return fallback; } };
  const write = (storage, key, value) => { try { storage.setItem(key, JSON.stringify(value)); } catch {} };
  const clamp = value => Math.max(0, Math.min(100, Number(value) || 0));
  let volume = clamp(read(localStorage, settingsKey, {bgm: 70}).bgm ?? 70);
  let muted = read(localStorage, muteKey, false) === true;
  let playing = null;
  const audio = document.createElement('audio');
  audio.id = 'train-bgm';
  audio.src = '/assets/audio/train-theme.mp3';
  audio.loop = true;
  audio.preload = 'auto';
  audio.hidden = true;
  audio.setAttribute('aria-hidden', 'true');
  audio.volume = volume / 100;
  audio.muted = muted;
  document.body.append(audio);

  function updateButtons() {
    document.querySelectorAll('[data-bgm-toggle]').forEach(button => {
      const off = muted || volume === 0;
      button.setAttribute('aria-pressed', String(off));
      button.setAttribute('aria-label', off ? '배경음악 켜기' : '배경음악 끄기');
      button.title = off ? '배경음악 켜기' : '배경음악 끄기';
      button.classList.toggle('audio-muted', off);
      let slash = button.querySelector('[data-bgm-slash]');
      if (!slash && button.querySelector('svg')) {
        slash=document.createElementNS('http://www.w3.org/2000/svg','path');
        slash.setAttribute('d','M3 3L21 21');slash.setAttribute('data-bgm-slash','');button.querySelector('svg').append(slash);
      }
      if (slash) slash.style.display = off ? '' : 'none';
    });
  }
  function play() {
    if (muted || volume === 0 || !audio.paused || playing) return playing;
    playing = audio.play().catch(() => {
      // Browser autoplay policies allow playback after the first user gesture.
    }).finally(() => { playing = null; });
    return playing;
  }
  function sync() {
    audio.volume = volume / 100;
    audio.muted = muted;
    if (muted || volume === 0) audio.pause(); else play();
    updateButtons();
    window.dispatchEvent(new CustomEvent('train-audio-change', {detail: {volume, muted}}));
  }
  function restorePosition() {
    const resume = read(sessionStorage, positionKey, null);
    if (resume && Number.isFinite(resume.time) && Number.isFinite(audio.duration) && audio.duration > 0) {
      const elapsed = Date.now() - resume.at;
      const continuity = resume.playing && elapsed >= 0 && elapsed < 15000 ? elapsed / 1000 : 0;
      audio.currentTime = (resume.time + continuity) % audio.duration;
    }
  }
  audio.addEventListener('loadedmetadata', () => {
    restorePosition();
    play();
  }, {once: true});
  window.addEventListener('pagehide', () => {
    write(sessionStorage, positionKey, {time: audio.currentTime, at: Date.now(), playing: !audio.paused});
    audio.pause();
  });
  window.addEventListener('pageshow', event => {
    volume = clamp(read(localStorage, settingsKey, {bgm: 70}).bgm ?? 70);
    muted = read(localStorage, muteKey, false) === true;
    if (event.persisted) restorePosition();
    sync();
  });
  document.addEventListener('pointerdown', play, {capture: true, passive: true});
  document.addEventListener('keydown', event => { if (!event.isComposing) play(); }, {capture: true});
  window.addEventListener('storage', event => {
    if (event.key === settingsKey) volume = clamp(read(localStorage, settingsKey, {bgm: 70}).bgm);
    if (event.key === muteKey) muted = read(localStorage, muteKey, false) === true;
    sync();
  });
  window.TrainAudio = Object.freeze({
    element: audio,
    getVolume: () => volume,
    isMuted: () => muted,
    setVolume(value) {
      volume = clamp(value);
      write(localStorage, settingsKey, {...read(localStorage, settingsKey, {}), bgm: volume});
      sync();
    },
    setMuted(value) { muted = !!value; write(localStorage, muteKey, muted); sync(); },
  });
  document.querySelectorAll('[data-bgm-toggle]').forEach(button => button.addEventListener('click', () => {
    const off = muted || volume === 0;
    if (volume === 0) window.TrainAudio.setVolume(70);
    window.TrainAudio.setMuted(!off);
  }));
  sync();
})();
