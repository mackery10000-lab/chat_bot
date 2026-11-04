// 캐릭터 이름 정하기 (승차권 발권)
(function () {
  const MAX = 8;
  const RANDOM_NAMES = ['한서윤', '도윤', '서하', '이안', '윤슬', '하람', '지오', '로운'];
  const NEXT_PAGE = '/chat';
  const STORAGE_KEY = 'noTerminus.playerName';

  const form = document.getElementById('nameForm');
  const input = document.getElementById('passengerName');
  const count = document.getElementById('count');
  const message = document.getElementById('message');
  const issueBtn = document.getElementById('issueBtn');
  const randomBtn = document.getElementById('randomBtn');
  const booth = document.querySelector('.booth');
  let issuing = false;

  // 이름 검사: 앞뒤 공백 제거 후 1~8자, 한글/영문/공백만
  function isValid(name) {
    return name.length > 0 && name.length <= MAX && /^[가-힣a-zA-Z ]+$/.test(name);
  }

  function update() {
    const name = input.value.trim();
    count.textContent = input.value.length;
    const ok = isValid(name);
    issueBtn.disabled = !ok || issuing;
    booth.classList.toggle('is-ready', ok);

    if (!name) {
      message.textContent = '성함을 적으면 승차권이 발권됩니다.';
    } else if (!ok) {
      message.textContent = '이름은 한글이나 영문으로만 적어 주십시오.';
    } else {
      message.innerHTML = '';
      const strong = document.createElement('span');
      strong.className = 'register-msg__name';
      strong.textContent = name; // 사용자가 입력한 값은 textContent로 (HTML 주입 방지)
      message.append(strong, ' 님 앞으로 승차권을 발권합니다.', document.createElement('br'), '이 열차는 종착지가 없습니다.');
    }
  }

  input.addEventListener('input', update);

  randomBtn.addEventListener('click', function () {
    input.value = RANDOM_NAMES[Math.floor(Math.random() * RANDOM_NAMES.length)];
    update();
    input.focus();
  });

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    const name = input.value.trim();
    if (!isValid(name)) return;

    if (issuing) return;
    issuing = true;

    // 다음 화면(게임)에서 쓸 수 있게 저장
    try { localStorage.setItem(STORAGE_KEY, name); } catch (err) { /* 저장 불가 환경 무시 */ }

    // 발권 연출: 이름 확정 → 도장 쾅 → 표가 빠져나감 → 다음 화면
    input.value = name;
    input.readOnly = true;
    issueBtn.disabled = true;
    randomBtn.disabled = true;
    booth.classList.add('is-printing');
    message.textContent = '발권 중…';
    const reduce = document.documentElement.classList.contains('no-fx') ||
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    setTimeout(function () {
      message.innerHTML = '';
      const strong = document.createElement('span');
      strong.className = 'register-msg__name';
      strong.textContent = name;
      message.append('발권 완료. ', strong, ' 님, 탑승하십시오.');
      booth.classList.add('is-issued');
    }, reduce ? 100 : 900);
    setTimeout(function () { window.location.href = NEXT_PAGE + '?new=1&username=' + encodeURIComponent(name); }, reduce ? 600 : 1900);
  });

  // 이전에 정한 이름이 있으면 채워두기
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) input.value = saved;
  } catch (err) { /* 무시 */ }

  update();
})();
