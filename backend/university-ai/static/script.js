const API_URL = "http://127.0.0.1:8000/api/ask";
const AUTH_URL = "http://127.0.0.1:8000/api/auth";
const LOGS_URL = "http://127.0.0.1:8000/api/logs";
const STORAGE_KEY = "chat_history_university";
const USER_KEY = "current_user";

const ROLE_HINTS = {
    applicant: { name: "Гость (абитуриент)", icon: "compass", desc: "Публичный доступ — агрегированная статистика приёма, направления, проходные баллы.", suggestions: ["Сколько бюджетных мест на «Экономике»?", "Какой средний проходной балл был в 2025 году?", "Сколько заявлений подано на «Информатику» в 2026?", "Какие направления подготовки есть в университете?"] },
    student: { name: "Студент", icon: "graduation-cap", desc: "Доступ к собственной успеваемости, задолженностям, расписанию и дисциплинам.", suggestions: ["Какой у меня средний балл за семестр?", "Есть ли у меня академические задолженности?", "Какие дисциплины у меня в этом семестре?", "Покажи расписание занятий"] },
    teacher: { name: "Преподаватель", icon: "book-open", desc: "Ваши дисциплины, группы, средний балл и учебная нагрузка.", suggestions: ["Сколько студентов записано на курс «Базы данных»?", "Какой средний балл по моей дисциплине?", "Сколько студентов не сдали экзамен?", "Какая у меня учебная нагрузка в этом семестре?"] },
    admin: { name: "Сотрудник / Администрация", icon: "building-2", desc: "Статистика по факультетам, приёмной кампании и отчётность (обезличенно).", suggestions: ["Сколько студентов обучается на факультете ИТ?", "Покажи динамику набора студентов за 5 лет", "Какая кафедра имеет наибольшую учебную нагрузку?", "Какова средняя заполняемость аудиторий?"] }
};

const USERS = {
    ivanov:  { password: "stud2026",  role: "student", name: "Иванов Иван", entity_id: 1, student_number: "ST-101" },
    petrova: { password: "teach2026", role: "teacher", name: "Петрова Анна Сергеевна", entity_id: 1, student_number: null },
    admin:   { password: "admin2026", role: "admin",   name: "Управление аналитики", entity_id: 1, student_number: null }
};

function getEl(id) {
    const el = document.getElementById(id);
    if (!el) console.warn(`⚠️ Элемент с id="${id}" не найден в HTML!`);
    return el;
}

function icon(name) { return `<i data-lucide="${name}"></i>`; }
function refreshIcons() { if (window.lucide) lucide.createIcons(); }

function escapeHtml(str) {
    if (str === null || str === undefined) return "";
    const div = document.createElement("div");
    div.textContent = String(str);
    return div.innerHTML;
}

function applyTheme(theme) {
    document.body.classList.toggle("light", theme === "light");
    const btn = getEl("themeBtn");
    if (btn) {
        btn.innerHTML = theme === "light" ? icon("moon") : icon("sun");
        btn.title = theme === "light" ? "Включить тёмную тему" : "Включить светлую тему";
    }
    localStorage.setItem("theme", theme);
    refreshIcons();
}

function toggleTheme() {
    const cur = localStorage.getItem("theme") || "dark";
    applyTheme(cur === "dark" ? "light" : "dark");
}

let userInputEl, sendBtnEl;
let currentUser = JSON.parse(localStorage.getItem(USER_KEY) || "null");
let chatHistory = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");

if (!currentUser) {
    currentUser = { role: "applicant", name: "Гость", auth: false };
}

document.addEventListener("DOMContentLoaded", () => {
    userInputEl = getEl("userInput");
    sendBtnEl = getEl("sendBtn");

    const savedTheme = localStorage.getItem("theme");
    const prefersLight = window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches;
    applyTheme(savedTheme || (prefersLight ? "light" : "dark"));

    updateHeaderBadge();
    if (chatHistory.length > 0) renderHistory();
    else renderWelcome();
    
    refreshIcons();
    if (userInputEl) userInputEl.focus();

    document.addEventListener("keydown", e => { if (e.key === "Escape") { closeLogin(); closeLogs(); } });
    getEl("loginModal")?.addEventListener("click", e => { if (e.target.id === "loginModal") closeLogin(); });
    getEl("logsModal")?.addEventListener("click", e => { if (e.target.id === "logsModal") closeLogs(); });

    if (userInputEl) {
        userInputEl.addEventListener("input", () => { autoResize(); updateSendState(); });
        userInputEl.addEventListener("keydown", e => {
            if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
        });
    }
    
    getEl("loginInput")?.addEventListener("keydown", e => { if (e.key === "Enter") doLogin(); });
    updateSendState();
});

function updateSendState() {
    if (userInputEl && sendBtnEl) {
        sendBtnEl.classList.toggle("disabled", !userInputEl.value.trim());
    }
}

function autoResize() {
    if (!userInputEl) return;
    userInputEl.style.height = "auto";
    userInputEl.style.height = Math.min(userInputEl.scrollHeight, 120) + "px";
}

function updateHeaderBadge() {
    const r = ROLE_HINTS[currentUser.role] || ROLE_HINTS.applicant;
    const badge = getEl("roleBadge");
    const btn = getEl("loginBtn");
    const logsBtn = getEl("logsBtn");

    if (badge) {
        badge.innerHTML = `${icon(r.icon)} <span class="badge-text">${r.name}</span>`;
        badge.title = r.name;
    }

    if (btn) {
        btn.innerHTML = currentUser.auth
            ? `${icon("log-out")} <span class="btn-text">Выйти</span>`
            : `${icon("log-in")} <span class="btn-text">Войти</span>`;
        btn.title = currentUser.auth ? "Выйти" : "Войти";
    }

    if (logsBtn) {
        logsBtn.style.display = (currentUser.auth && currentUser.role === "admin") ? "inline-flex" : "none";
    }

    refreshIcons();
}

function openLogin() {
    if (currentUser.auth) {
        if (confirm("Выйти из учётной записи и вернуться к гостевому доступу?")) {
            currentUser = { role: "applicant", name: "Гость", auth: false };
            localStorage.setItem(USER_KEY, JSON.stringify(currentUser));
            updateHeaderBadge();
            renderWelcome();
        }
        return;
    }
    const err = getEl("loginError");
    const loginIn = getEl("loginInput");
    const passIn = getEl("passwordInput");
    
    if (err) err.innerHTML = "";
    if (loginIn) loginIn.value = "";
    if (passIn) passIn.value = "";
    
    const modal = getEl("loginModal");
    if (modal) {
        modal.style.display = "flex";
        if (loginIn) setTimeout(() => loginIn.focus(), 100);
    }
}

function closeLogin() {
    const modal = getEl("loginModal");
    if (modal) modal.style.display = "none";
}

function doLogin() {
    const login = getEl("loginInput")?.value.trim() || "";
    const pass = getEl("passwordInput")?.value || "";
    const err = getEl("loginError");
    if (err) err.innerHTML = "";

    const acc = USERS[login];
    if (!acc || acc.password !== pass) {
        if (err) {
            err.innerHTML = `${icon("triangle-alert")} Неверный логин или пароль.`;
            refreshIcons();
        }
        return;
    }

    currentUser = { role: acc.role, name: acc.name, login, entity_id: acc.entity_id, student_number: acc.student_number, auth: true };
    localStorage.setItem(USER_KEY, JSON.stringify(currentUser));
    closeLogin();
    updateHeaderBadge();
    renderWelcome();
}

function useSuggestion(el) {
    if (!userInputEl) return;
    userInputEl.value = el.textContent;
    autoResize();
    updateSendState();
    sendMessage();
}

function clearHistory() {
    if (confirm("Очистить историю сообщений?")) {
        chatHistory = [];
        localStorage.removeItem(STORAGE_KEY);
        renderWelcome();
    }
}

function renderWelcome() {
    const container = getEl("chatMessages");
    if (!container) return;
    const r = ROLE_HINTS[currentUser.role] || ROLE_HINTS.applicant;
    const greeting = currentUser.auth ? `, ${escapeHtml(currentUser.name)}` : "";
    
    container.innerHTML = `
        <div class="welcome-message">
            <div class="welcome-icon">${icon(r.icon)}</div>
            <h3>Здравствуйте${greeting}!</h3>
            <p>${r.desc}</p>
            <div class="suggestions">
                ${r.suggestions.map(s => `<div class="suggestion" onclick="useSuggestion(this)">${escapeHtml(s)}</div>`).join("")}
            </div>
        </div>`;
    refreshIcons();
}

function renderHistory() {
    const container = getEl("chatMessages");
    if (!container) return;
    container.innerHTML = "";
    chatHistory.forEach(msg => addMessageToDOM(msg));
}

function addMessageToDOM(msg) {
    const container = getEl("chatMessages");
    if (!container) return;

    const div = document.createElement("div");
    div.className = `message ${msg.role}`;
    const avatar = msg.role === "user" ? icon("user-round") : icon("sparkles");
    let contentHTML = `<div>${escapeHtml(msg.content)}</div>`;

    if (msg.role === "bot") {
        if (msg.error) {
            contentHTML = `<div class="error-message">${icon("triangle-alert")} ${escapeHtml(msg.error)}</div>`;
        } else {
            if (msg.sql) {
                contentHTML += `<div class="sql-block"><div class="sql-header"><span>${icon("database")} SQL-запрос</span><button onclick="copySQL(this)">${icon("copy")} Копировать</button></div><pre><code class="language-sql">${escapeHtml(msg.sql)}</code></pre></div>`;
            }
            if (msg.data && Array.isArray(msg.data) && msg.data.length > 0) {
                contentHTML += renderTable(msg.data);
                contentHTML += `<button class="csv-btn" onclick="exportCSV(this)">${icon("download")} Экспорт в CSV</button>`;
            } else if (msg.sql) {
                contentHTML += `<div style="margin-top:8px;color:#94a3b8;font-style:italic;">${icon("check")} Запрос выполнен. Данные не найдены.</div>`;
            }
        }
    }

    div.innerHTML = `<div class="avatar">${avatar}</div><div class="message-content">${contentHTML}</div>`;
    container.appendChild(div);
    
    if (msg.sql && window.hljs) {
        const codeEl = div.querySelector("code.language-sql");
        if (codeEl) hljs.highlightElement(codeEl);
    }
    refreshIcons();
    setTimeout(() => { container.scrollTop = container.scrollHeight; }, 50);
}

function renderTable(data) {
    if (!data || !Array.isArray(data) || data.length === 0) return "";
    const headers = Object.keys(data[0]);
    let html = `<div class="result-table"><table><thead><tr>`;
    headers.forEach(h => html += `<th>${escapeHtml(h)}</th>`);
    html += `</tr></thead><tbody>`;
    data.forEach(row => {
        html += `<tr>`;
        headers.forEach(h => html += `<td>${escapeHtml(String(row[h] ?? ""))}</td>`);
        html += `</tr>`;
    });
    return html + `</tbody></table></div>`;
}

function copySQL(btn) {
    const codeBlock = btn.closest(".sql-block")?.querySelector("code");
    if (!codeBlock) return;
    navigator.clipboard.writeText(codeBlock.textContent).then(() => {
        btn.innerHTML = `${icon("check")} Скопировано`;
        refreshIcons();
        setTimeout(() => { btn.innerHTML = `${icon("copy")} Копировать`; refreshIcons(); }, 2000);
    });
}

function exportCSV(btn) {
    const table = btn.parentElement?.querySelector("table");
    if (!table) return;
    let csv = "\uFEFF"; 
    table.querySelectorAll("tr").forEach(row => {
        csv += Array.from(row.querySelectorAll("th,td")).map(c => `"${c.textContent.replace(/"/g, '""')}"`).join(",") + "\n";
    });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob([csv], {type: "text/csv;charset=utf-8;"}));
    link.download = `data_${Date.now()}.csv`;
    link.click();
}

async function sendMessage() {
    if (!userInputEl) return;
    const text = userInputEl.value.trim();
    if (!text) return;

    addMessageToDOM({role: "user", content: text});
    chatHistory.push({role: "user", content: text});
    
    userInputEl.value = "";
    autoResize();
    updateSendState();
    userInputEl.focus();

    const typingEl = getEl("typingIndicator");
    if (typingEl) typingEl.style.display = "flex";
    
    const box = getEl("chatMessages");
    if (box) box.scrollTop = box.scrollHeight;

    try {
        const response = await fetch(API_URL, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                question: text,
                user_role: currentUser.role,
                user_name: currentUser.name || "",
                entity_id: currentUser.entity_id || null,
                student_number: currentUser.student_number || null
            })
        });
        
        const result = await response.json();
        if (typingEl) typingEl.style.display = "none";

        let botMsg;
        if (response.ok && result.status === "ok" && !result.error) {
            const rows = result.data?.rows || (Array.isArray(result.data) ? result.data : []);
            botMsg = { role: "bot", content: result.answer || "Готово!", sql: result.sql || null, data: rows };
        } else {
            botMsg = { role: "bot", content: "Ошибка", error: result.detail || result.error || "Не удалось выполнить запрос" };
        }
        addMessageToDOM(botMsg);
        chatHistory.push(botMsg);
    } catch (err) {
        console.error("Fetch error:", err);
        if (typingEl) typingEl.style.display = "none";
        const botMsg = { role: "bot", content: "Ошибка сети", error: "Не удалось подключиться к серверу. Убедитесь, что Python-бэкенд запущен на порту 8000." };
        addMessageToDOM(botMsg);
        chatHistory.push(botMsg);
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(chatHistory));
}

// ===== ЛОГИ =====
function openLogs() {
    if (!currentUser.auth || currentUser.role !== "admin") {
        alert("Доступ к логам есть только у администраторов");
        return;
    }
    const modal = getEl("logsModal");
    if (modal) { modal.style.display = "flex"; loadLogs(); }
}

function closeLogs() {
    const modal = getEl("logsModal");
    if (modal) modal.style.display = "none";
}

async function loadLogs() {
    const linesEl = getEl("logsLines");
    const filterEl = getEl("logsFilter");
    const contentEl = getEl("logsContent");
    const statsEl = getEl("logsStats");
    
    if (!contentEl) return;
    contentEl.textContent = "Загрузка логов...";
    
    try {
        const response = await fetch(LOGS_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ 
                lines: linesEl ? parseInt(linesEl.value) || 100 : 100, 
                filter: filterEl ? filterEl.value.trim() : "",
                user_role: currentUser.role
            })
        });
        
        const result = await response.json();
        
        if (!response.ok || !result.success) {
            contentEl.textContent = "Ошибка: " + (result.detail || "Не удалось загрузить логи");
            if (statsEl) statsEl.innerHTML = "";
            return;
        }
        
        if (result.stats && statsEl) {
            statsEl.innerHTML = `
                Всего записей: <b>${result.stats.total_lines}</b> | 
                Вопросов: <b>${result.stats.questions}</b> | 
                Ошибок: <b style="color:#f87171;">${result.stats.errors}</b> | 
                Заблокировано: <b style="color:#fbbf24;">${result.stats.blocked}</b>
            `;
        }
        
        if (result.lines && result.lines.length > 0) {
            contentEl.textContent = result.lines.join("\n");
        } else {
            contentEl.textContent = "Логи пусты или не найдены по заданному фильтру.";
        }
    } catch (e) {
        console.error("Load logs error:", e);
        contentEl.textContent = "Ошибка соединения с сервером: " + e.message;
    }
}

window.toggleTheme = toggleTheme;
window.openLogin = openLogin;
window.closeLogin = closeLogin;
window.doLogin = doLogin;
window.clearHistory = clearHistory;
window.useSuggestion = useSuggestion;
window.copySQL = copySQL;
window.exportCSV = exportCSV;
window.openLogs = openLogs;
window.closeLogs = closeLogs;
window.loadLogs = loadLogs;