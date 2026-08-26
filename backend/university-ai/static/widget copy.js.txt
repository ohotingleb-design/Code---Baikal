(function() {
  const API_URL = window.UNIVERSITY_AI_API || window.location.origin + '/api/ask';
  
  const widget = document.createElement('div');
  widget.innerHTML = `
    <div id="uai-btn" style="position:fixed;bottom:24px;right:24px;width:60px;height:60px;border-radius:50%;
      background:linear-gradient(135deg,#667eea,#764ba2);display:flex;align-items:center;justify-content:center;
      cursor:pointer;box-shadow:0 4px 20px rgba(0,0,0,.3);z-index:9999;font-size:28px;color:#fff;">🎓</div>
    <div id="uai-chat" style="position:fixed;bottom:100px;right:24px;width:380px;height:520px;background:#fff;
      border-radius:16px;box-shadow:0 10px 40px rgba(0,0,0,.25);display:none;flex-direction:column;overflow:hidden;z-index:9999;">
      <div style="background:linear-gradient(90deg,#667eea,#764ba2);color:#fff;padding:14px;display:flex;justify-content:space-between;align-items:center;">
        <div style="font-weight:600;">🎓 AI Ассистент Университета</div>
        <div id="uai-close" style="cursor:pointer;font-size:20px;">✕</div>
      </div>
      <div id="uai-msgs" style="flex:1;overflow-y:auto;padding:12px;background:#f8f9fa;font-family:system-ui;font-size:14px;"></div>
      <div style="padding:10px;border-top:1px solid #e1e5eb;display:flex;gap:6px;">
        <input id="uai-input" placeholder="Задайте вопрос..." style="flex:1;padding:8px 12px;border:1px solid #cbd5e1;border-radius:8px;font-size:14px;"/>
        <button id="uai-send" style="background:#667eea;color:#fff;border:none;border-radius:8px;padding:0 14px;cursor:pointer;">➤</button>
      </div>
    </div>
  `;
  document.body.appendChild(widget);

  const btn = widget.querySelector('#uai-btn');
  const chat = widget.querySelector('#uai-chat');
  const close = widget.querySelector('#uai-close');
  const msgs = widget.querySelector('#uai-msgs');
  const input = widget.querySelector('#uai-input');
  const send = widget.querySelector('#uai-send');

  btn.onclick = () => { chat.style.display = chat.style.display === 'flex' ? 'none' : 'flex'; btn.style.display='none'; };
  close.onclick = () => { chat.style.display = 'none'; btn.style.display = 'flex'; };

  function add(html, cls) {
    const d = document.createElement('div');
    d.style.cssText = 'margin-bottom:8px;padding:8px 10px;border-radius:8px;max-width:85%;white-space:pre-wrap;';
    if (cls === 'u') { d.style.marginLeft='auto'; d.style.background='#667eea'; d.style.color='#fff'; }
    else { d.style.background='#fff'; d.style.border='1px solid #e1e5eb'; }
    d.innerHTML = html;
    msgs.appendChild(d);
    msgs.scrollTop = msgs.scrollHeight;
    return d;
  }

  async function ask() {
    const q = input.value.trim();
    if (!q) return;
    add(q, 'u');
    input.value = '';
    const t = add('⏳ Думаю...', 'b');
    try {
      const r = await fetch(API_URL, {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({question: q, user_role: 'student'})
      });
      const j = await r.json();
      t.remove();
      let html = (j.answer || '').replace(/\n/g, '<br>');
      if (j.data && j.data.rows && j.data.rows.length) {
        html += '<table style="border-collapse:collapse;margin-top:6px;font-size:12px;width:100%;">';
        html += '<tr>' + j.data.columns.map(c => '<th style="border:1px solid #cbd5e1;padding:4px;background:#e2e8f0;">' + c + '</th>').join('') + '</tr>';
        html += j.data.rows.map(r => '<tr>' + j.data.columns.map(c => '<td style="border:1px solid #cbd5e1;padding:4px;">' + (r[c] ?? '—') + '</td>').join('') + '</tr>').join('');
        html += '</table>';
      }
      add(html, 'b');
    } catch (e) { t.remove(); add('❌ Ошибка', 'b'); }
  }
  send.onclick = ask;
  input.addEventListener('keydown', e => { if (e.key === 'Enter') ask(); });
  add('👋 Привет! Я AI-ассистент университета. Задайте вопрос.', 'b');
})();