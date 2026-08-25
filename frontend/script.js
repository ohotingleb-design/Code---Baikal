const API_URL = "http://localhost:8000/api/query";
const STORAGE_KEY = "chat_history_university";
const USER_KEY = "current_user";

// ===== РОЛИ (Lucide-иконки — единый стиль) =====
const ROLE_HINTS = {
    applicant: {
        name: "Гость (абитуриент)", icon: "compass",
        description: "Публичный доступ — агрегированная статистика приёма, направления, проходные баллы.",
        suggestions: [
            "Сколько бюджетных мест на направлении «Экономика»?",
            "Какой средний проходной балл был в 2025 году?",
            "Сколько заявлений подано на «Информатика» в 2026?",
            "Какие направления подготовки есть в университете?"
        ]
    },
    student: {
        name: "Студент", icon: "graduation-cap",
        description: "Доступ к собственной успеваемости, задолженностям, расписанию и дисциплинам.",
        suggestions: [
            "Какой у меня средний балл за семестр?",
            "Есть ли у меня академические задолженности?",
            "Какие дисциплины у меня в этом семестре?",
            "Покажи расписание занятий"
        ]
    },
    teacher: {
        name: "Преподаватель", icon: "book-open",
        description: "Ваши дисциплины, группы, средний балл и учебная нагрузка.",
        suggestions: [
            "Сколько студентов записано на курс «Базы данных»?",
            "Какой средний балл по моей дисциплине?",
            "Сколько студентов не сдали экзамен?",
            "Какая у меня учебная нагрузка в этом семестре?"
        ]
    },
    admin: {
        name: "Сотрудник / Администрация", icon: "building-2",
        description: "Статистика по факультетам, приёмной кампании и отчётность (обезличенно).",
        suggestions: [
            "Сколько студентов обучается на факультете ИТ?",
            "Покажи динамику набора студентов за 5 лет",
            "Какая кафедра имеет наибольшую учебную нагрузку?",
            "Какова средняя заполняемость аудиторий?"
        ]
    }
};

// ===== УЧЁТНЫЕ ЗАПИСИ (логин + пароль; демо для защиты) =====
const USERS = {
    ivanov:  { password: "stud2026",  role: "student", name: "Иванов Иван",
               entity_id: 1, student_number: "ST-101" },
    petrova: { password: "teach2026", role: "teacher", name: "Петрова Анна Сергеевна",
               entity_id: 1, student_number: null },
    admin:   { password: "admin2026", role: "admin",   name: "Управление аналитики",
               entity_id: 1, student_number: null }
};

// ===== ХЕЛПЕРЫ ИКОНОК =====
function icon(name) { return `<i data-lucide="${name}"></i>`; }
function refreshIcons() { if (window.lucide) lucide.createIcons(); }

let currentUser = JSON.parse(localStorage.getItem(USER_KEY) || "null");
let chatHistory = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");

// === ИНИЦИАЛИЗАЦИЯ ===
document.addEventListener("DOMContentLoaded", () => {
    if (!currentUser) {
        currentUser = { role: "applicant", name: "Гость", auth: false };
    }
    updateHeaderBadge();
    if (chatHistory.length > 0) renderHistory();
    else renderWelcome();
    refreshIcons();
    document.getElementById("userInput").focus();
});

// === ШАПКА: бейдж и кнопка (адаптивно: текст в span, скрывается на мобильных) ===
function updateHeaderBadge() {
    const r = ROLE_HINTS[currentUser.role] || ROLE_HINTS.applicant;
    const badge = document.getElementById("roleBadge");
    const btn   = document.getElementById("loginBtn");

    badge.innerHTML = `${icon(r.icon)} <span class="badge-text">${r.name}</span>`;
    badge.title = r.name;

    btn.innerHTML = currentUser.auth
        ? `${icon("log-out")} <span class="btn-text">Выйти</span>`
        : `${icon("log-in")} <span class="btn-text">Войти</span>`;
    btn.title = currentUser.auth ? "Выйти" : "Войти";

    refreshIcons();
}

// === МОДАЛКА ВХОДА (логин + пароль) ===
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
    document.getElementById("loginError").innerHTML = "";
    document.getElementById("loginInput").value = "";
    document.getElementById("passwordInput").value = "";
    document.getElementById("loginModal").style.display = "flex";
    document.getElementById("loginInput").focus();
}

function closeLogin() {
    document.getElementById("loginModal").style.display = "none";
}

function doLogin() {
    const login = document.getElementById("loginInput").value.trim();
    const pass  = document.getElementById("passwordInput").value;
    const err   = document.getElementById("loginError");
    err.innerHTML = "";

    const acc = USERS[login];
    if (!acc || acc.password !== pass) {
        err.innerHTML = `${icon("triangle-alert")} Неверный логин или пароль.`;
        refreshIcons();
        return;
    }

    currentUser = {
        role: acc.role,
        name: acc.name,
        login: login,
        entity_id: acc.entity_id,
        student_number: acc.student_number,
        auth: true
    };
    localStorage.setItem(USER_KEY, JSON.stringify(currentUser));
    closeLogin();
    updateHeaderBadge();
    renderWelcome();
}

// === ЧАТ ===
function autoResize(el) {
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 120) + "px";
}
function handleKeyPress(e) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
}
function useSuggestion(el) {
    document.getElementById("userInput").value = el.textContent;
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
    const r = ROLE_HINTS[currentUser.role] || ROLE_HINTS.applicant;
    document.getElementById("chatMessages").innerHTML = `
        <div class="welcome-message">
            <div class="welcome-icon">${icon(r.icon)}</div>
            <h3>Здравствуйте!</h3>
            <p>${r.description}</p>
            <div class="suggestions">
                ${r.suggestions.map(s => `<div class="suggestion" onclick="useSuggestion(this)">${s}</div>`).join("")}
            </div>
        </div>`;
    refreshIcons();
}

function renderHistory() {
    document.getElementById("chatMessages").innerHTML = "";
    chatHistory.forEach(msg => addMessageToDOM(msg));
}

function addMessageToDOM(msg) {
    const container = document.getElementById("chatMessages");
    const div = document.createElement("div");
    div.className = `message ${msg.role}`;
    const avatar = msg.role === "user" ? icon("user-round") : icon("sparkles");
    let contentHTML = `<div>${escapeHtml(msg.content)}</div>`;

    if (msg.role === "bot") {
        if (msg.error) {
            contentHTML = `<div class="error-message">${icon("triangle-alert")} ${escapeHtml(msg.error)}</div>`;
        } else {
            if (msg.sql) {
                contentHTML += `
                <div class="sql-block">
                    <div class="sql-header">
                        <span>${icon("database")} SQL-запрос</span>
                        <button onclick="copySQL(this)">${icon("copy")} Копировать</button>
                    </div>
                    <pre><code class="language-sql">${escapeHtml(msg.sql)}</code></pre>
                </div>`;
            }
            if (msg.data && msg.data.length > 0) {
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
    container.scrollTop = container.scrollHeight;
}

function renderTable(data) {
    if (!data || !data.length) return "";
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
    navigator.clipboard.writeText(btn.closest(".sql-block").querySelector("code").textContent);
    btn.innerHTML = `${icon("check")} Скопировано`;
    refreshIcons();
    setTimeout(() => { btn.innerHTML = `${icon("copy")} Копировать`; refreshIcons(); }, 2000);
}

function exportCSV(btn) {
    const table = btn.previousElementSibling.querySelector("table");
    if (!table) return;
    let csv = "";
    table.querySelectorAll("tr").forEach(row => {
        csv += Array.from(row.querySelectorAll("th,td"))
            .map(c => `"${c.textContent.replace(/"/g, '""')}"`).join(",") + "\n";
    });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob([csv], {type: "text/csv;charset=utf-8;"}));
    link.download = `data_${Date.now()}.csv`;
    link.click();
}

async function sendMessage() {
    const input = document.getElementById("userInput");
    const text = input.value.trim();
    if (!text) return;

    addMessageToDOM({role: "user", content: text});
    chatHistory.push({role: "user", content: text});
    input.value = ""; autoResize(input);

    document.getElementById("typingIndicator").style.display = "flex";
    const box = document.getElementById("chatMessages");
    box.scrollTop = box.scrollHeight;

    try {
        const response = await fetch(API_URL, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                question: text,
                role: currentUser.role,
                user_name: currentUser.name || "",
                entity_id: currentUser.entity_id || null,
                student_number: currentUser.student_number || null
            })
        });
        const result = await response.json();
        document.getElementById("typingIndicator").style.display = "none";

        let botMsg;
        if (response.ok && !result.error) {
            botMsg = {role: "bot", content: "Готово!", sql: result.sql, data: result.data};
        } else {
            botMsg = {role: "bot", content: "Ошибка",
                      error: result.detail || result.error || "Не удалось выполнить запрос"};
        }
        addMessageToDOM(botMsg);
        chatHistory.push(botMsg);
    } catch (err) {
        document.getElementById("typingIndicator").style.display = "none";
        const botMsg = {role: "bot", content: "Ошибка сети",
                        error: "Не удалось подключиться к серверу. Проверьте, что бэкенд запущен."};
        addMessageToDOM(botMsg);
        chatHistory.push(botMsg);
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(chatHistory));
}

function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}