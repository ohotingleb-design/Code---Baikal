(function() {
  'use strict';

  // ===== КОНФИГ =====
  const API_URL = window.UNIVERSITY_AI_API || window.location.origin + '/api/ask';
  const STORAGE_KEY = 'uai_theme';
  const USER_KEY = 'uai_user';
  const HISTORY_KEY = 'uai_history';

  // ===== РОЛИ =====
  const ROLES = {
    applicant: { name: 'Гость', icon: 'compass', desc: 'Публичный доступ к статистике приёма.' },
    student:   { name: 'Студент', icon: 'graduation-cap', desc: 'Моя успеваемость и дисциплины.' },
    teacher:   { name: 'Преподаватель', icon: 'book-open', desc: 'Мои дисциплины и нагрузка.' },
    admin:     { name: 'Администрация', icon: 'building-2', desc: 'Отчётность по факультетам.' }
  };

  const USERS = {
    ivanov:  { password: 'stud2026',  role: 'student', name: 'Иванов Иван', entity_id: 1, student_number: 'ST-101' },
    petrova: { password: 'teach2026', role: 'teacher', name: 'Петрова А.С.', entity_id: 1, student_number: null },
    admin:   { password: 'admin2026', role: 'admin',   name: 'Администрация', entity_id: 1, student_number: null }
  };

  // ===== ДИНАМИЧЕСКАЯ ЗАГРУЗКА CDN =====
  function loadScript(src) {
    return new Promise((res, rej) => {
      if (document.querySelector(`script[src="${src}"]`)) return res();
      const s = document.createElement('script');
      s.src = src; s.onload = res; s.onerror = rej;
      document.head.appendChild(s);
    });
  }
  function loadStyle(href) {
    if (document.querySelector(`link[href="${href}"]`)) return;
    const l = document.createElement('link');
    l.rel = 'stylesheet'; l.href = href;
    document.head.appendChild(l);
  }

  Promise.all([
    loadScript('https://unpkg.com/lucide@latest'),
    loadScript('https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js'),
    loadStyle('https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/atom-one-dark.min.css')
  ]).then(init);

  // ===== СТИЛИ =====
  const STYLES = `
  .uai-root { font-family:-apple-system,BlinkMacSystemFont,'SF Pro Display','Segoe UI',Roboto,sans-serif; }
  .uai-root *, .uai-root *::before, .uai-root *::after { box-sizing:border-box; }

  /* Кнопка-плашка */
  .uai-btn {
    position:fixed; bottom:24px; right:24px; width:60px; height:60px; border-radius:50%;
    background:rgba(124,58,237,.85); backdrop-filter:blur(16px); -webkit-backdrop-filter:blur(16px);
    border:1px solid rgba(255,255,255,.25); color:#fff; cursor:pointer; z-index:99999;
    display:flex; align-items:center; justify-content:center; font-size:26px;
    box-shadow:0 10px 30px rgba(124,58,237,.4), inset 0 1px 0 rgba(255,255,255,.3);
    transition:transform .2s;
  }
  .uai-btn:hover { transform:scale(1.08); }
  .uai-btn .lucide { width:26px; height:26px; stroke-width:2; stroke:currentColor; fill:none; stroke-linecap:round; stroke-linejoin:round; }

  /* Окно чата */
  .uai-chat {
    position:fixed; bottom:100px; right:24px; width:420px; height:600px; max-height:80vh;
    background:rgba(20,25,55,.55); backdrop-filter:blur(30px) saturate(160%); -webkit-backdrop-filter:blur(30px) saturate(160%);
    border:1px solid rgba(255,255,255,.18); border-radius:20px; z-index:99999;
    display:none; flex-direction:column; overflow:hidden;
    box-shadow:0 30px 80px rgba(0,0,0,.5), inset 0 1px 0 rgba(255,255,255,.2);
    color:#e2e8f0;
  }
  .uai-chat.open { display:flex; animation:uaiSlide .25s ease; }
  @keyframes uaiSlide { from{opacity:0; transform:translateY(10px)} to{opacity:1; transform:translateY(0)} }

  /* Шапка */
  .uai-head {
    background:rgba(255,255,255,.08); border-bottom:1px solid rgba(255,255,255,.12);
    padding:12px 14px; display:flex; justify-content:space-between; align-items:center; gap:8px;
  }
  .uai-head-title { display:flex; align-items:center; gap:8px; font-weight:600; font-size:14px; }
  .uai-head-title .lucide { width:18px; height:18px; color:#a5b4fc; }
  .uai-head-actions { display:flex; gap:6px; }
  .uai-ibtn {
    width:32px; height:32px; border-radius:50%; border:1px solid rgba(255,255,255,.18);
    background:rgba(255,255,255,.10); color:#fff; cursor:pointer;
    display:flex; align-items:center; justify-content:center; transition:all .2s;
  }
  .uai-ibtn:hover { background:rgba(255,255,255,.22); }
  .uai-ibtn .lucide { width:14px; height:14px; }

  /* Бейдж роли */
  .uai-role {
    font-size:10px; padding:2px 8px; border-radius:999px;
    background:rgba(255,255,255,.08); border:1px solid rgba(255,255,255,.12);
    color:rgba(255,255,255,.7); display:inline-flex; align-items:center; gap:4px;
    margin-left:6px;
  }
  .uai-role .lucide { width:10px; height:10px; }

  /* Лента */
  .uai-msgs { flex:1; overflow-y:auto; padding:14px; background:transparent; }
  .uai-msgs::-webkit-scrollbar { width:5px; }
  .uai-msgs::-webkit-scrollbar-thumb { background:rgba(255,255,255,.2); border-radius:3px; }

  .uai-msg { margin-bottom:12px; display:flex; gap:8px; animation:uaiSlide .25s ease; }
  .uai-msg.u { flex-direction:row-reverse; }
  .uai-av {
    width:30px; height:30px; border-radius:50%; flex-shrink:0;
    background:rgba(255,255,255,.12); border:1px solid rgba(255,255,255,.18);
    display:flex; align-items:center; justify-content:center;
  }
  .uai-av .lucide { width:14px; height:14px; color:#c4b5fd; }
  .uai-bubble {
    max-width:78%; padding:10px 12px; border-radius:14px; font-size:13px; line-height:1.5;
    background:rgba(255,255,255,.10); border:1px solid rgba(255,255,255,.14);
    backdrop-filter:blur(12px); -webkit-backdrop-filter:blur(12px);
    box-shadow:0 4px 14px rgba(0,0,0,.2), inset 0 1px 0 rgba(255,255,255,.15);
    word-wrap:break-word;
  }
  .uai-msg.u .uai-bubble {
    background:linear-gradient(135deg, rgba(37,99,235,.7), rgba(124,58,237,.7));
    border-color:rgba(255,255,255,.25); color:#fff; border-radius:14px 14px 4px 14px;
  }
  .uai-msg.b .uai-bubble { border-radius:14px 14px 14px 4px; }

  /* Приветствие */
  .uai-welcome { text-align:center; padding:20px 10px; color:#cbd5e1; }
  .uai-welcome .lucide { width:40px; height:40px; color:#a5b4fc; margin-bottom:8px; }
  .uai-welcome h4 { color:#f8fafc; margin-bottom:6px; font-size:14px; }
  .uai-welcome p { font-size:12px; margin-bottom:12px; }
  .uai-sugg {
    display:block; width:100%; text-align:left; margin-bottom:6px;
    background:rgba(255,255,255,.06); border:1px solid rgba(255,255,255,.14);
    color:#bfdbfe; padding:8px 10px; border-radius:10px; font-size:12px; cursor:pointer;
    transition:all .2s;
  }
  .uai-sugg:hover { background:rgba(255,255,255,.14); transform:translateX(3px); }

  /* SQL-блок */
  .uai-sql { margin-top:8px; background:rgba(2,6,23,.7); border:1px solid rgba(255,255,255,.1); border-radius:10px; overflow:hidden; }
  .uai-sql-head { background:rgba(255,255,255,.06); color:#cbd5e1; padding:4px 10px; font-size:10px; display:flex; justify-content:space-between; align-items:center; }
  .uai-sql-head button { background:transparent; border:none; color:#94a3b8; cursor:pointer; font-size:10px; }
  .uai-sql pre { margin:0; padding:10px; overflow-x:auto; }
  .uai-sql code { font-family:Consolas,Monaco,monospace; font-size:11px; background:transparent; }

  /* Таблица */
  .uai-tbl { margin-top:8px; overflow-x:auto; border-radius:8px; border:1px solid rgba(255,255,255,.12); background:rgba(255,255,255,.04); }
  .uai-tbl table { width:100%; border-collapse:collapse; font-size:11px; }
  .uai-tbl th { background:rgba(255,255,255,.08); padding:6px 8px; text-align:left; color:#e2e8f0; border-bottom:1px solid rgba(255,255,255,.12); }
  .uai-tbl td { padding:6px 8px; color:#dbeafe; border-bottom:1px solid rgba(255,255,255,.06); }
  .uai-csv { margin-top:6px; padding:4px 10px; border-radius:999px; font-size:11px; cursor:pointer;
    background:rgba(37,99,235,.6); color:#fff; border:1px solid rgba(255,255,255,.2); }

  .uai-err { background:rgba(220,38,38,.25) !important; color:#fecaca !important; border-color:rgba(248,113,113,.4) !important; }

  /* Индикатор */
  .uai-typing { display:flex; gap:4px; padding:4px 0; }
  .uai-typing span { width:6px; height:6px; background:rgba(255,255,255,.6); border-radius:50%; animation:uaiDot 1.2s infinite; }
  .uai-typing span:nth-child(2){animation-delay:.15s} .uai-typing span:nth-child(3){animation-delay:.3s}
  @keyframes uaiDot { 0%,60%,100%{transform:translateY(0);opacity:.5} 30%{transform:translateY(-5px);opacity:1} }

  /* Ввод */
  .uai-input-bar {
    padding:10px; border-top:1px solid rgba(255,255,255,.1);
    background:rgba(255,255,255,.04); backdrop-filter:blur(16px);
    display:flex; gap:6px; align-items:flex-end;
  }
  .uai-input {
    flex:1; background:rgba(255,255,255,.08); border:1px solid rgba(255,255,255,.15);
    color:#f8fafc; border-radius:10px; padding:8px 10px; font-size:13px; outline:none; resize:none;
    max-height:80px; font-family:inherit;
  }
  .uai-input::placeholder { color:rgba(241,245,249,.4); }
  .uai-send {
    width:36px; height:36px; border-radius:50%; border:none; cursor:pointer;
    background:linear-gradient(135deg,#3b82f6,#8b5cf6); color:#fff;
    display:flex; align-items:center; justify-content:center;
    box-shadow:inset 0 1px 0 rgba(255,255,255,.4), 0 6px 16px rgba(59,130,246,.4);
    transition:transform .2s;
  }
  .uai-send:hover { transform:scale(1.08); }
  .uai-send .lucide { width:16px; height:16px; }
  .uai-send:disabled { opacity:.4; cursor:not-allowed; transform:none; }

  /* Модалка входа */
  .uai-modal {
    position:absolute; inset:0; background:rgba(8,10,30,.7); backdrop-filter:blur(6px);
    display:none; align-items:center; justify-content:center; padding:16px; z-index:10;
  }
  .uai-modal.open { display:flex; }
  .uai-modal-card {
    background:rgba(20,25,55,.85); border:1px solid rgba(255,255,255,.2); border-radius:16px;
    padding:18px; width:100%; max-width:320px; backdrop-filter:blur(30px);
    box-shadow:0 20px 60px rgba(0,0,0,.5);
  }
  .uai-modal-card h4 { margin:0 0 4px; font-size:14px; color:#f8fafc; display:flex; align-items:center; gap:6px; }
  .uai-modal-card h4 .lucide { width:16px; height:16px; color:#a5b4fc; }
  .uai-modal-card p { font-size:11px; color:#94a3b8; margin:0 0 10px; }
  .uai-modal-card label { font-size:11px; color:#cbd5e1; display:block; margin-top:6px; }
  .uai-modal-card input {
    width:100%; padding:8px 10px; border-radius:8px; border:1px solid rgba(255,255,255,.18);
    background:rgba(255,255,255,.08); color:#f8fafc; font-size:13px; outline:none; margin-top:3px;
  }
  .uai-modal-card input:focus { border-color:#8b5cf6; }
  .uai-modal-err { color:#fca5a5; font-size:11px; margin-top:6px; min-height:14px; }
  .uai-modal-hint { font-size:10px; color:#94a3b8; background:rgba(255,255,255,.05); border:1px dashed rgba(255,255,255,.15);
    border-radius:8px; padding:6px 8px; margin:8px 0; line-height:1.5; }
  .uai-modal-btn {
    width:100%; padding:9px; border:none; border-radius:10px; cursor:pointer; font-size:13px; font-weight:600;
    background:linear-gradient(135deg,#3b82f6,#8b5cf6); color:#fff; margin-top:8px;
    box-shadow:inset 0 1px 0 rgba(255,255,255,.3);
  }

  /* Светлая тема */
  .uai-root.light .uai-chat { background:rgba(255,255,255,.75); color:#334155; border-color:rgba(30,41,59,.1); }
  .uai-root.light .uai-head { background:rgba(255,255,255,.6); border-color:rgba(30,41,59,.08); }
  .uai-root.light .uai-head-title { color:#1e293b; }
  .uai-root.light .uai-ibtn { background:rgba(255,255,255,.7); border-color:rgba(30,41,59,.12); color:#1e293b; }
  .uai-root.light .uai-ibtn:hover { background:#fff; }
  .uai-root.light .uai-role { background:rgba(30,41,59,.06); border-color:rgba(30,41,59,.1); color:rgba(30,41,59,.65); }
  .uai-root.light .uai-bubble { background:rgba(255,255,255,.7); border-color:rgba(30,41,59,.1); color:#334155; }
  .uai-root.light .uai-msg.u .uai-bubble { color:#fff; }
  .uai-root.light .uai-welcome { color:#475569; }
  .uai-root.light .uai-welcome h4 { color:#1e293b; }
  .uai-root.light .uai-sugg { background:rgba(255,255,255,.7); border-color:rgba(30,41,59,.1); color:#2563eb; }
  .uai-root.light .uai-sql { background:rgba(15,23,42,.92); }
  .uai-root.light .uai-tbl { background:rgba(255,255,255,.7); border-color:rgba(30,41,59,.1); }
  .uai-root.light .uai-tbl th { background:rgba(30,41,59,.05); color:#334155; }
  .uai-root.light .uai-tbl td { color:#334155; }
  .uai-root.light .uai-input-bar { background:rgba(255,255,255,.5); border-color:rgba(30,41,59,.08); }
  .uai-root.light .uai-input { background:rgba(255,255,255,.8); border-color:rgba(30,41,59,.12); color:#1e293b; }
  .uai-root.light .uai-input::placeholder { color:rgba(71,85,105,.5); }
  .uai-root.light .uai-modal-card { background:rgba(255,255,255,.85); color:#334155; border-color:rgba(30,41,59,.12); }
  .uai-root.light .uai-modal-card h4 { color:#1e293b; }
  .uai-root.light .uai-modal-card label { color:#475569; }
  .uai-root.light .uai-modal-card input { background:rgba(255,255,255,.8); border-color:rgba(30,41,59,.12); color:#1e293b; }
  .uai-root.light .uai-modal-hint { color:#64748b; background:rgba(30,41,59,.04); border-color:rgba(30,41,59,.12); }

  /* Мобильные */
  @media (max-width:500px) {
    .uai-chat { bottom:0; right:0; left:0; width:100%; height:100%; max-height:100%; border-radius:0; }
    .uai-btn { bottom:16px; right:16px; width:54px; height:54px; }
  }
  `;

  // ===== HTML =====
  const HTML = `
    <div class="uai-root" id="uaiRoot">
      <button class="uai-btn" id="uaiBtn" aria-label="Открыть ассистент">
        <i data-lucide="graduation-cap"></i>
      </button>

      <div class="uai-chat" id="uaiChat">
        <div class="uai-head">
          <div class="uai-head-title">
            <i data-lucide="graduation-cap"></i>
            <span>AI Ассистент</span>
            <span class="uai-role" id="uaiRole"><i data-lucide="compass"></i> Гость</span>
          </div>
          <div class="uai-head-actions">
            <button class="uai-ibtn" id="uaiTheme" title="Тема" aria-label="Сменить тему"><i data-lucide="sun"></i></button>
            <button class="uai-ibtn" id="uaiLoginBtn" title="Войти" aria-label="Войти"><i data-lucide="log-in"></i></button>
            <button class="uai-ibtn" id="uaiClear" title="Очистить" aria-label="Очистить"><i data-lucide="trash-2"></i></button>
          </div>
        </div>

        <div class="uai-msgs" id="uaiMsgs"></div>

        <div class="uai-input-bar">
          <textarea class="uai-input" id="uaiInput" placeholder="Задайте вопрос..." rows="1"></textarea>
          <button class="uai-send" id="uaiSend" aria-label="Отправить"><i data-lucide="arrow-up"></i></button>
        </div>

        <!-- Модалка входа -->
        <div class="uai-modal" id="uaiModal">
          <div class="uai-modal-card">
            <h4><i data-lucide="lock-keyhole"></i> Вход в систему</h4>
            <p>Для студентов, преподавателей и сотрудников</p>
            <label>Логин</label>
            <input type="text" id="uaiLogin" placeholder="ivanov">
            <label>Пароль</label>
            <input type="password" id="uaiPass" placeholder="stud2026">
            <div class="uai-modal-err" id="uaiErr"></div>
            <div class="uai-modal-hint">
              студент — <b>ivanov / stud2026</b><br>
              преподаватель — <b>petrova / teach2026</b><br>
              админ — <b>admin / admin2026</b>
            </div>
            <button class="uai-modal-btn" id="uaiDoLogin">Войти</button>
          </div>
        </div>
      </div>
    </div>
  `;

  // ===== ИНИЦИАЛИЗАЦИЯ =====
  function init() {
    const style = document.createElement('style');
    style.textContent = STYLES;
    document.head.appendChild(style);

    const wrap = document.createElement('div');
    wrap.innerHTML = HTML;
    document.body.appendChild(wrap);

    const root = wrap.querySelector('#uaiRoot');
    const btn = wrap.querySelector('#uaiBtn');
    const chat = wrap.querySelector('#uaiChat');
    const msgs = wrap.querySelector('#uaiMsgs');
    const input = wrap.querySelector('#uaiInput');
    const send = wrap.querySelector('#uaiSend');
    const themeBtn = wrap.querySelector('#uaiTheme');
    const loginBtn = wrap.querySelector('#uaiLoginBtn');
    const clearBtn = wrap.querySelector('#uaiClear');
    const roleEl = wrap.querySelector('#uaiRole');
    const modal = wrap.querySelector('#uaiModal');
    const modalClose = () => modal.classList.remove('open');

    let user = JSON.parse(localStorage.getItem(USER_KEY) || 'null') || { role: 'applicant', name: 'Гость', auth: false };
    let history = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]');

    // Тема
    function applyTheme(t) {
      root.classList.toggle('light', t === 'light');
      themeBtn.innerHTML = t === 'light' ? '<i data-lucide="moon"></i>' : '<i data-lucide="sun"></i>';
      localStorage.setItem(STORAGE_KEY, t);
      if (window.lucide) lucide.createIcons();
    }
    applyTheme(localStorage.getItem(STORAGE_KEY) ||
      (window.matchMedia && matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'));
    themeBtn.onclick = () => applyTheme(root.classList.contains('light') ? 'dark' : 'light');

    // Открытие/закрытие
    btn.onclick = () => { chat.classList.add('open'); btn.style.display = 'none'; setTimeout(()=>input.focus(), 100); };
    // Крестик в шапке — сделаем через двойной клик по иконке (упрощённо: кнопка сворачивает)
    // Добавим кнопку закрытия динамически в шапку:
    const closeBtn = document.createElement('button');
    closeBtn.className = 'uai-ibtn';
    closeBtn.innerHTML = '<i data-lucide="x"></i>';
    closeBtn.title = 'Свернуть';
    closeBtn.onclick = () => { chat.classList.remove('open'); btn.style.display = 'flex'; };
    wrap.querySelector('.uai-head-actions').appendChild(closeBtn);

    // Бейдж роли
    function updateRole() {
      const r = ROLES[user.role] || ROLES.applicant;
      roleEl.innerHTML = `<i data-lucide="${r.icon}"></i> ${r.name}`;
      loginBtn.innerHTML = user.auth ? '<i data-lucide="log-out"></i>' : '<i data-lucide="log-in"></i>';
      if (window.lucide) lucide.createIcons();
    }
    updateRole();

    // Вход
    loginBtn.onclick = () => {
      if (user.auth) {
        if (confirm('Выйти из учётной записи?')) {
          user = { role: 'applicant', name: 'Гость', auth: false };
          localStorage.setItem(USER_KEY, JSON.stringify(user));
          updateRole(); renderWelcome();
        }
        return;
      }
      modal.classList.add('open');
      wrap.querySelector('#uaiLogin').value = '';
      wrap.querySelector('#uaiPass').value = '';
      wrap.querySelector('#uaiErr').textContent = '';
      setTimeout(()=>wrap.querySelector('#uaiLogin').focus(), 50);
    };
    modal.onclick = e => { if (e.target === modal) modalClose(); };
    wrap.querySelector('#uaiDoLogin').onclick = doLogin;
    wrap.querySelector('#uaiPass').onkeydown = e => { if (e.key === 'Enter') doLogin(); };

    function doLogin() {
      const l = wrap.querySelector('#uaiLogin').value.trim();
      const p = wrap.querySelector('#uaiPass').value;
      const err = wrap.querySelector('#uaiErr');
      const acc = USERS[l];
      if (!acc || acc.password !== p) { err.textContent = ' Неверный логин или пароль'; return; }
      user = { role: acc.role, name: acc.name, login: l, entity_id: acc.entity_id, student_number: acc.student_number, auth: true };
      localStorage.setItem(USER_KEY, JSON.stringify(user));
      modalClose(); updateRole(); renderWelcome();
    }

    // Очистка
    clearBtn.onclick = () => {
      if (confirm('Очистить историю?')) {
        history = []; localStorage.removeItem(HISTORY_KEY); renderWelcome();
      }
    };

    // Подсказки
    function renderWelcome() {
      const r = ROLES[user.role] || ROLES.applicant;
      const suggs = {
        applicant: ['Сколько бюджетных мест на Информатике?', 'Какой средний проходной балл в 2025?'],
        student:   ['Какой у меня средний балл?', 'Есть ли у меня задолженности?'],
        teacher:   ['Сколько студентов на моём курсе?', 'Какой средний балл по дисциплине?'],
        admin:     ['Сколько студентов на факультете ИТ?', 'Динамика набора за 5 лет']
      };
      msgs.innerHTML = `
        <div class="uai-welcome">
          <i data-lucide="${r.icon}"></i>
          <h4>Здравствуйте!</h4>
          <p>${r.desc}</p>
          ${suggs[user.role].map(s => `<button class="uai-sugg" data-q="${s.replace(/"/g,'&quot;')}">${s}</button>`).join('')}
        </div>`;
      msgs.querySelectorAll('.uai-sugg').forEach(b => b.onclick = () => { input.value = b.dataset.q; sendMsg(); });
      if (window.lucide) lucide.createIcons();
    }

    if (history.length) history.forEach(m => addMsg(m));
    else renderWelcome();

    // Кнопка отправки
    function updSend() { send.disabled = !input.value.trim(); }
    input.addEventListener('input', () => { updSend(); input.style.height='auto'; input.style.height=Math.min(input.scrollHeight,80)+'px'; });
    updSend();

    send.onclick = sendMsg;
    input.onkeydown = e => { if (e.key==='Enter' && !e.shiftKey) { e.preventDefault(); sendMsg(); } };

    function addMsg(m) {
      const div = document.createElement('div');
      div.className = 'uai-msg ' + m.role;
      const avIcon = m.role === 'u' ? 'user-round' : 'sparkles';
      let html = `<div class="uai-av"><i data-lucide="${avIcon}"></i></div><div class="uai-bubble">`;

      if (m.role === 'u') {
        html += escapeHtml(m.content);
      } else {
        if (m.error) {
          html += `<div class="uai-err">⚠ ${escapeHtml(m.error)}</div>`;
        } else {
          html += escapeHtml(m.content || '');
          if (m.sql) {
            html += `<div class="uai-sql"><div class="uai-sql-head"><span>SQL</span><button data-copy="1">Копировать</button></div><pre><code class="language-sql">${escapeHtml(m.sql)}</code></pre></div>`;
          }
          if (m.data && m.data.length) {
            const cols = Object.keys(m.data[0]);
            html += `<div class="uai-tbl"><table><thead><tr>${cols.map(c=>`<th>${escapeHtml(c)}</th>`).join('')}</tr></thead><tbody>`;
            m.data.forEach(r => { html += `<tr>${cols.map(c=>`<td>${escapeHtml(String(r[c]??''))}</td>`).join('')}</tr>`; });
            html += `</tbody></table></div><button class="uai-csv" data-csv="1">⬇ CSV</button>`;
          }
        }
      }
      html += `</div>`;
      div.innerHTML = html;
      msgs.appendChild(div);

      // Подсветка SQL
      if (m.sql && window.hljs) {
        const code = div.querySelector('code.language-sql');
        if (code) hljs.highlightElement(code);
      }
      // Копирование
      const cp = div.querySelector('[data-copy]');
      if (cp) cp.onclick = () => { navigator.clipboard.writeText(m.sql); cp.textContent='✓'; setTimeout(()=>cp.textContent='Копировать',1500); };
      // CSV
      const csv = div.querySelector('[data-csv]');
      if (csv) csv.onclick = () => {
        const tbl = csv.previousElementSibling.querySelector('table');
        let s = ''; tbl.querySelectorAll('tr').forEach(r => { s += Array.from(r.querySelectorAll('th,td')).map(c=>`"${c.textContent.replace(/"/g,'""')}"`).join(',')+'\n'; });
        const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([s],{type:'text/csv'})); a.download=`data_${Date.now()}.csv`; a.click();
      };

      if (window.lucide) lucide.createIcons();
      msgs.scrollTop = msgs.scrollHeight;
    }

    async function sendMsg() {
      const q = input.value.trim();
      if (!q) return;
      const userMsg = { role: 'u', content: q };
      addMsg(userMsg); history.push(userMsg);
      input.value = ''; input.style.height='auto'; updSend(); input.focus();

      const typing = document.createElement('div');
      typing.className = 'uai-msg b';
      typing.innerHTML = `<div class="uai-av"><i data-lucide="sparkles"></i></div><div class="uai-bubble"><div class="uai-typing"><span></span><span></span><span></span></div></div>`;
      msgs.appendChild(typing); msgs.scrollTop = msgs.scrollHeight;

      try {
        const r = await fetch(API_URL, {
          method: 'POST',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify({
            question: q,
            role: user.role,
            user_name: user.name || '',
            entity_id: user.entity_id || null,
            student_number: user.student_number || null
          })
        });
        const j = await r.json();
        typing.remove();
        let botMsg;
        if (r.ok && !j.error) {
          botMsg = { role: 'b', content: 'Готово!', sql: j.sql, data: j.data };
        } else {
          botMsg = { role: 'b', content: 'Ошибка', error: j.detail || j.error || 'Не удалось выполнить запрос' };
        }
        addMsg(botMsg); history.push(botMsg);
      } catch (e) {
        typing.remove();
        addMsg({ role: 'b', content: 'Ошибка сети', error: 'Не удалось подключиться к серверу' });
      }
      localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
    }

    function escapeHtml(s) {
      const d = document.createElement('div'); d.textContent = s; return d.innerHTML;
    }
  }
})();