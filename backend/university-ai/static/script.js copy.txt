const API_URL = "/api/ask";
const AUTH_URL = "/api/auth";
const STATS_URL = "/api/stats";
const STORAGE_KEY = "chat_history_university";
const USER_KEY = "current_user";

// ===== РОЛИ =====
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
        name: "Администратор", icon: "building-2",
        description: "Статистика по факультетам, приёмной кампании и отчётность (обезличенно).",
        suggestions: [
            "Сколько студентов обучается на факультете ИТ?",
            "Покажи динамику набора студентов за 5 лет",
            "Какая кафедра имеет наибольшую учебную нагрузку?",
            "Какова средняя заполняемость аудиторий?"
        ]
    }
};

// ===== ХЕЛПЕРЫ =====
function icon(name) { return '<i data-lucide="' + name + '"></i>'; }
function refreshIcons() { if (window.lucide) lucide.createIcons(); }

function escapeHtml(str) {
    var div = document.createElement("div");
    div.textContent = String(str);
    return div.innerHTML;
}

// ===== ✅ НОВОЕ: ТЕМЫ =====
function applyTheme(theme) {
    document.body.classList.toggle("light", theme === "light");
    var btn = document.getElementById("themeBtn");
    if (btn) {
        btn.innerHTML = theme === "light" ? icon("moon") : icon("sun");
        btn.title = theme === "light" ? "Включить тёмную тему" : "Включить светлую тему";
    }
    localStorage.setItem("theme", theme);
    refreshIcons();
}

function toggleTheme() {
    var cur = localStorage.getItem("theme") || "dark";
    var newTheme = cur === "dark" ? "light" : "dark";
    console.log("Переключаю тему:", cur, "->", newTheme);
    console.log("body классы ДО:", document.body.className);
    applyTheme(newTheme);
    console.log("body классы ПОСЛЕ:", document.body.className);
}

// ===== СОСТОЯНИЕ =====
var currentUser = JSON.parse(localStorage.getItem(USER_KEY) || "null");
var chatHistory = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");

if (!currentUser) {
    currentUser = { role: "applicant", name: "Гость", auth: false };
}

// ===== ИНИЦИАЛИЗАЦИЯ =====
document.addEventListener("DOMContentLoaded", function() {
    // ✅ НОВОЕ: применяем тему
    applyTheme(localStorage.getItem("theme") ||
        (window.matchMedia && matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark"));

    updateHeaderBadge();
    if (chatHistory.length > 0) {
        renderHistory();
    } else {
        renderWelcome();
    }
    refreshIcons();

    var input = document.getElementById("userInput");
    if (input) {
        input.focus();
        input.addEventListener("keydown", handleKeyPress);
        input.addEventListener("input", function() { autoResize(input); });
    }

    var sendBtn = document.getElementById("sendBtn");
    if (sendBtn) {
        sendBtn.addEventListener("click", sendMessage);
    }

    // UX: закрытие модалки по Esc и клику по фону
    document.addEventListener("keydown", function(e) { if (e.key === "Escape") closeLogin(); });
    var loginModal = document.getElementById("loginModal");
    if (loginModal) {
        loginModal.addEventListener("click", function(e) {
            if (e.target.id === "loginModal") closeLogin();
        });
    }
});

// ===== ШАПКА =====
function updateHeaderBadge() {
    var r = ROLE_HINTS[currentUser.role] || ROLE_HINTS.applicant;
    var badge = document.getElementById("roleBadge");
    var btn = document.getElementById("loginBtn");

    if (badge) {
        badge.innerHTML = icon(r.icon) + ' <span class="badge-text">' + r.name + '</span>';
        badge.title = r.name;
    }

    if (btn) {
        if (currentUser.auth) {
            btn.innerHTML = icon("log-out") + ' <span class="btn-text">Выйти</span>';
            btn.title = "Выйти";
        } else {
            btn.innerHTML = icon("log-in") + ' <span class="btn-text">Войти</span>';
            btn.title = "Войти";
        }
    }
    refreshIcons();
}

// ===== МОДАЛКА ВХОДА =====
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
    var login = document.getElementById("loginInput").value.trim();
    var pass = document.getElementById("passwordInput").value;
    var err = document.getElementById("loginError");
    err.innerHTML = "";

    fetch(AUTH_URL, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({login: login, password: pass})
    })
    .then(function(r) { return r.json(); })
    .then(function(result) {
        if (!result.success) {
            err.innerHTML = icon("triangle-alert") + " " + (result.detail || "Неверный логин или пароль.");
            refreshIcons();
            return;
        }
        currentUser = {
            role: result.role,
            name: result.name,
            login: login,
            entity_id: result.entity_id,
            student_number: result.student_number,
            auth: true
        };
        localStorage.setItem(USER_KEY, JSON.stringify(currentUser));
        closeLogin();
        updateHeaderBadge();
        renderWelcome();
    })
    .catch(function() {
        err.innerHTML = icon("triangle-alert") + " Ошибка соединения с сервером.";
        refreshIcons();
    });
}

// ===== РАБОТА С ТЕКСТОМ =====
function autoResize(el) {
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 120) + "px";
}

function handleKeyPress(e) {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
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

// ===== РЕНДЕРИНГ =====
function renderWelcome() {
    var r = ROLE_HINTS[currentUser.role] || ROLE_HINTS.applicant;
    document.getElementById("chatMessages").innerHTML =
        '<div class="welcome-message">' +
            '<div class="welcome-icon">' + icon(r.icon) + '</div>' +
            '<h3>Здравствуйте!</h3>' +
            '<p>' + r.description + '</p>' +
            '<div class="suggestions">' +
                r.suggestions.map(function(s) {
                    return '<div class="suggestion" onclick="useSuggestion(this)">' + s + '</div>';
                }).join("") +
            '</div>' +
        '</div>';
    refreshIcons();
}

function renderHistory() {
    document.getElementById("chatMessages").innerHTML = "";
    chatHistory.forEach(addMessageToDOM);
}

function addMessageToDOM(msg) {
    var container = document.getElementById("chatMessages");
    var div = document.createElement("div");
    div.className = "message " + msg.role;
    var avatar = msg.role === "user" ? icon("user-round") : icon("sparkles");
    var contentHTML = "<div>" + escapeHtml(msg.content) + "</div>";

    if (msg.role === "bot") {
        if (msg.error) {
            contentHTML = '<div class="error-message">' + icon("triangle-alert") + " " + escapeHtml(msg.error) + '</div>';
        } else {
            if (msg.sql) {
                contentHTML +=
                    '<div class="sql-block">' +
                        '<div class="sql-header">' +
                            '<span>' + icon("database") + ' SQL-запрос</span>' +
                            '<button onclick="copySQL(this)">' + icon("copy") + ' Копировать</button>' +
                        '</div>' +
                        '<pre><code class="language-sql">' + escapeHtml(msg.sql) + '</code></pre>' +
                    '</div>';
            }
            if (msg.data && msg.data.length > 0) {
                contentHTML += renderTable(msg.data);
                contentHTML += '<button class="csv-btn" onclick="exportCSV(this)">' + icon("download") + ' Экспорт в CSV</button>';
            } else if (msg.sql) {
                contentHTML += '<div style="margin-top:8px;color:#94a3b8;font-style:italic;">' + icon("check") + ' Запрос выполнен. Данные не найдены.</div>';
            }
        }
    }

    div.innerHTML = '<div class="avatar">' + avatar + '</div><div class="message-content">' + contentHTML + '</div>';
    container.appendChild(div);

    if (msg.sql && window.hljs) {
        var codeEl = div.querySelector("code.language-sql");
        if (codeEl) hljs.highlightElement(codeEl);
    }
    refreshIcons();

    setTimeout(function() {
        div.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }, 100);
}

function renderTable(data) {
    if (!data || !data.length) return "";
    var headers = Object.keys(data[0]);
    var html = '<div class="result-table"><table><thead><tr>';
    headers.forEach(function(h) { html += "<th>" + escapeHtml(h) + "</th>"; });
    html += '</tr></thead><tbody>';
    data.forEach(function(row) {
        html += "<tr>";
        headers.forEach(function(h) {
            var v = row[h];
            html += "<td>" + escapeHtml(v == null ? "" : String(v)) + "</td>";
        });
        html += "</tr>";
    });
    return html + '</tbody></table></div>';
}

function copySQL(btn) {
    var code = btn.closest(".sql-block").querySelector("code");
    navigator.clipboard.writeText(code.textContent);
    btn.innerHTML = icon("check") + " Скопировано";
    refreshIcons();
    setTimeout(function() {
        btn.innerHTML = icon("copy") + " Копировать";
        refreshIcons();
    }, 2000);
}

function exportCSV(btn) {
    var table = btn.previousElementSibling.querySelector("table");
    if (!table) return;
    var csv = "";
    table.querySelectorAll("tr").forEach(function(row) {
        var cells = Array.from(row.querySelectorAll("th,td"));
        csv += cells.map(function(c) {
            return '"' + c.textContent.replace(/"/g, '""') + '"';
        }).join(",") + "\n";
    });
    var link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob([csv], {type: "text/csv;charset=utf-8;"}));
    link.download = "data_" + Date.now() + ".csv";
    link.click();
}

// ===== ОТПРАВКА СООБЩЕНИЯ =====
function sendMessage() {
    var input = document.getElementById("userInput");
    var text = input.value.trim();
    if (!text) return;

    addMessageToDOM({role: "user", content: text});
    chatHistory.push({role: "user", content: text});
    input.value = "";
    autoResize(input);

    document.getElementById("typingIndicator").style.display = "flex";

    fetch(API_URL, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            question: text,
            user_role: currentUser.role,
            user_name: currentUser.name || "",
            student_number: currentUser.student_number || null,
            entity_id: currentUser.entity_id || null
        })
    })
    .then(function(r) { return r.json(); })
    .then(function(result) {
        document.getElementById("typingIndicator").style.display = "none";
        var botMsg;
        if (result.status === "ok") {
            botMsg = {
                role: "bot",
                content: result.answer || "Готово!",
                sql: result.sql,
                data: (result.data && result.data.rows) ? result.data.rows : []
            };
        } else {
            botMsg = {
                role: "bot",
                content: "Ошибка",
                error: result.answer || "Не удалось выполнить запрос"
            };
        }
        addMessageToDOM(botMsg);
        chatHistory.push(botMsg);
        localStorage.setItem(STORAGE_KEY, JSON.stringify(chatHistory));
    })
    .catch(function() {
        document.getElementById("typingIndicator").style.display = "none";
        var botMsg = {
            role: "bot",
            content: "Ошибка сети",
            error: "Не удалось подключиться к серверу."
        };
        addMessageToDOM(botMsg);
        chatHistory.push(botMsg);
        localStorage.setItem(STORAGE_KEY, JSON.stringify(chatHistory));
    });
}

// Глобальные функции для inline-обработчиков в HTML (onclick)
window.openLogin = openLogin;
window.closeLogin = closeLogin;
window.doLogin = doLogin;
window.clearHistory = clearHistory;
window.useSuggestion = useSuggestion;
window.copySQL = copySQL;
window.exportCSV = exportCSV;
// ✅ НОВОЕ: функция темы тоже глобальная
window.toggleTheme = toggleTheme;