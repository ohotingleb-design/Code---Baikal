import asyncio
import logging
import re
import time
import os
from decimal import Decimal
from datetime import datetime, date

from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import psycopg
from psycopg.rows import dict_row
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# ================= НАСТРОЙКИ (из .env или переменных окружения) =================
YANDEX_API_KEY = os.getenv("YANDEX_API_KEY", "AQVN3awuGYT3gVtFGwyg3bTjsy77sfriDgnFxM_W")
FOLDER_ID = os.getenv("FOLDER_ID", "b1gq8ef571dtt80m92rs")
MODEL_URI = f"gpt://{FOLDER_ID}/yandexgpt-lite/latest"

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "university_db")
DB_USER = os.getenv("DB_USER", "db11_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "12345")

MAX_ROWS = 50
LARGE_THRESHOLD = 20
TIMEOUT_SEC = 10

# ================= ЛОГИРОВАНИЕ В ФАЙЛ =================
logging.basicConfig(
    filename="app.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    encoding="utf-8"
)
logger = logging.getLogger("uni-ai")

# ================= ИНИЦИАЛИЗАЦИЯ =================
client = OpenAI(
    api_key=YANDEX_API_KEY,
    base_url="https://ai.api.cloud.yandex.net/v1"
)
app = FastAPI(title="University AI Assistant - Kod Baikala")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================= SYSTEM PROMPT (полный) =================
SYSTEM_PROMPT = """Ты — AI-ассистент университета для хакатона "Код Байкала".
Преобразуй вопросы на русском языке в безопасные SQL-запросы к PostgreSQL.

СХЕМА БАЗЫ ДАННЫХ:
faculties(id, name) — факультеты
departments(id, faculty_id, name) — кафедры
programs(id, faculty_id, name, budget_places, paid_places) — направления подготовки
teachers(id, full_name, department_id) — преподаватели (ФИО разрешены)
students(id, student_id_number, group_name, faculty_id, enrollment_year) — студенты
applicants(id, application_year, program_id, total_score, is_admitted) — абитуриенты
courses(id, name, teacher_id, semester) — дисциплины
grades(id, student_id, course_id, grade, is_passed) — оценки
admins(id, full_name, position) — администраторы (ФИО разрешены)

СВЯЗИ:
grades.student_id = students.id
grades.course_id = courses.id
courses.teacher_id = teachers.id
teachers.department_id = departments.id
students.faculty_id = faculties.id
applicants.program_id = programs.id
programs.faculty_id = faculties.id
departments.faculty_id = faculties.id

БЕЗОПАСНОСТЬ (КРИТИЧНО!):
1. ТОЛЬКО SELECT (или WITH ... SELECT). INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE — вежливый отказ без SQL.
2. ЗАПРЕЩЕНО выводить: student_id_number, ФИО студентов, ФИО абитуриентов, списки конкретных студентов.
3. Данные студентов/абитуриентов — ТОЛЬКО через агрегаты COUNT/AVG/SUM/MIN/MAX + GROUP BY.
4. РАЗРЕШЕНО выводить ФИО: teachers.full_name, admins.full_name.
5. НЕ выдумывай данные и таблицы.
6. При поиске по конкретным названиям используй ILIKE с подстрокой: ILIKE '%слово%'.
7. Для агрегатов БЕЗ GROUP BY НЕ добавляй LIMIT.
8. Для сырых списков или агрегатов с GROUP BY добавляй LIMIT 50.

РОЛИ ПОЛЬЗОВАТЕЛЕЙ:
- Абитуриент: направления, бюджет/платные места, проходной балл.
- Студент: свои оценки, средний балл, задолженности.
- Преподаватель: свои дисциплины, количество студентов, средний балл.
- Декан/администрация: численность по факультетам, динамика набора (обезличенно).

ПЕРСОНАЛИЗАЦИЯ (КРИТИЧНО!):
9. Если в контексте указан пользователь (например: student_id_number='ST-00001', students.id=1)
   и он спрашивает про "мои оценки / мой средний балл / мои задолженности / мои дисциплины" —
   ОБЯЗАТЕЛЬНО добавь WHERE grades.student_id = <id>.
   СВОИ данные пользователю видеть РАЗРЕШЕНО.
10. Если пользователь НЕ авторизован и просит "мои оценки" —
    не выдумывай, а ответом попроси войти через кнопку "Войти".

ПРИМЕРЫ СЛОЖНЫХ ЗАПРОСОВ:

Вопрос: "Сколько студентов обучается на каждом факультете?"
<sql>
SELECT f.name AS faculty, COUNT(s.id) AS student_count
FROM faculties f
LEFT JOIN students s ON s.faculty_id = f.id
GROUP BY f.id, f.name
ORDER BY student_count DESC
</sql>

Вопрос: "Покажи динамику набора студентов за последние 5 лет"
<sql>
WITH yearly_counts AS (
  SELECT enrollment_year AS year, COUNT(*) AS students
  FROM students
  WHERE enrollment_year >= 2021
  GROUP BY enrollment_year
)
SELECT year, students
FROM yearly_counts
ORDER BY year
</sql>

Вопрос: "Статистика поступлений за последние 5 лет"
<sql>
SELECT 
    application_year AS год,
    COUNT(*) AS всего_заявлений,
    COUNT(CASE WHEN is_admitted = true THEN 1 END) AS поступило
FROM applicants
WHERE application_year >= 2021
GROUP BY application_year
ORDER BY application_year DESC
</sql>

ФОРМАТ ОТВЕТА (СТРОГО В ЭТОМ ПОРЯДКЕ):

ОБЪЯСНЕНИЕ:
- Таблицы: [список]
- JOIN: [какие и зачем]
- Фильтры: [WHERE условия]
- Агрегаты: [функции или "нет"]
- Ограничения: [LIMIT N или "не требуется"]

<sql>
[один SELECT запрос, без комментариев внутри SQL]
</sql>

ОТВЕТ: [короткий понятный ответ на русском языке на основе данных, которые вернёт запрос]

ВАЖНО: SQL всегда должен быть внутри тегов <sql>...</sql>. Без SQL не отвечай.
Если вопрос не про данные БД — всё равно сгенерируй простой SQL типа SELECT 'Привет! Я готов помочь.' AS answer.
"""

WHITELIST = {"faculties", "departments", "programs", "teachers",
             "students", "applicants", "courses", "grades", "admins"}
FORBIDDEN = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
             "CREATE", "GRANT", "EXEC", "COPY", "PG_SLEEP", "SLEEP",
             "XP_", "SHUTDOWN", "INTO OUTFILE", "INTO DUMPFILE"]


def fix_encoding(text):
    if not isinstance(text, str):
        return text
    try:
        fixed = text.encode('cp1251').decode('utf-8')
        cyrillic_fixed = sum(1 for c in fixed if 'а' <= c <= 'я' or 'А' <= c <= 'Я' or c == 'ё' or c == 'Ё')
        cyrillic_orig = sum(1 for c in text if 'а' <= c <= 'я' or 'А' <= c <= 'Я' or c == 'ё' or c == 'Ё')
        if cyrillic_fixed > cyrillic_orig:
            return fixed
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return text


def extract_sql(text):
    m = re.search(r"<sql>\s*(.*?)\s*</sql>", text, re.S | re.I)
    if m:
        sql = m.group(1).strip()
        sql = re.sub(r"^```sql\s*", "", sql, flags=re.I)
        sql = re.sub(r"\s*```$", "", sql, flags=re.I)
        return sql.strip()
    
    m = re.search(r"```sql\s*(.*?)\s*```", text, re.S | re.I)
    if m:
        return m.group(1).strip()
    
    m = re.search(r"(SELECT\b.*?)(?:\n\n|\Z)", text, re.S | re.I)
    if m:
        sql = m.group(1).strip()
        if (sql.startswith('"') and sql.endswith('"')) or (sql.startswith("'") and sql.endswith("'")):
            inner = sql[1:-1]
            if "'" not in inner and '"' not in inner:
                sql = inner
        return sql
    
    return None


def validate_sql(sql):
    if not sql:
        return False, "Empty SQL", None
    
    s = str(sql).strip().rstrip(";").strip()
    up = s.upper()
    
    if not (up.lstrip().startswith("SELECT") or up.lstrip().startswith("WITH")):
        return False, "Only SELECT or WITH (CTE) allowed", None
    
    for kw in FORBIDDEN:
        if re.search(r"\b" + kw + r"\b", up):
            return False, "Forbidden keyword: " + kw, None
    
    if re.search(r"\bUNION\b.*\b(INSERT|UPDATE|DELETE|DROP)\b", up):
        return False, "UNION with modification queries forbidden", None
    
    if "--" in s or "/*" in s or ";" in s:
        return False, "Comments and compound queries forbidden", None
    
    cte_names = {m.lower() for m in re.findall(r"\bWITH\s+([a-zA-Z_]\w*)\s+AS\s*\(", s, re.I)}
    cte_names |= {m.lower() for m in re.findall(r",\s*([a-zA-Z_]\w*)\s+AS\s*\(", s, re.I)}

    tables = {t.lower().strip('"') for t in re.findall(r"(?:FROM|JOIN)\s+\"?([a-zA-Z_]\w*)\"?", s)}
    bad = tables - WHITELIST - cte_names
    if bad:
        return False, "Tables outside whitelist: " + ", ".join(sorted(bad)), None
    
    has_agg = any(f in up for f in ("COUNT(", "AVG(", "SUM(", "MIN(", "MAX("))
    has_group = "GROUP BY" in up
    
    if "LIMIT" not in up and not has_agg:
        s += " LIMIT " + str(MAX_ROWS)
    elif "LIMIT" not in up and has_agg and has_group:
        s += " LIMIT " + str(MAX_ROWS)
    
    return True, "ok", s


def run_db(sql):
    if isinstance(sql, bytes):
        sql = sql.decode('utf-8', errors='replace')
    
    cleaned = []
    for c in sql:
        code = ord(c)
        if c in '\n\t' or (code >= 32 and code != 127 and code != 0xFEFF):
            cleaned.append(c)
    sql = ''.join(cleaned)
    
    logger.info("Executing SQL: %s", sql[:300])
    
    conn = psycopg.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASSWORD, row_factory=dict_row
    )
    
    try:
        cur = conn.cursor()
        try:
            cur.execute(f"SET statement_timeout = '{TIMEOUT_SEC}s'")
        except Exception:
            pass
        
        cur.execute(sql)
        
        if not cur.description:
            return [], []
        
        cols = [d.name for d in cur.description]
        raw_rows = cur.fetchall()
        
        rows = []
        for r in raw_rows:
            row = {}
            for col in cols:
                v = r[col]
                if v is None:
                    row[col] = None
                elif isinstance(v, (int, float, bool)):
                    row[col] = v
                elif isinstance(v, Decimal):
                    row[col] = float(v)
                elif isinstance(v, (date, datetime)):
                    row[col] = v.isoformat()
                elif isinstance(v, bytes):
                    row[col] = v.decode('utf-8', errors='replace')
                else:
                    row[col] = str(v)
            rows.append(row)
        
        return cols, rows
    finally:
        conn.close()


def clean_value(v):
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if v is None:
        return None
    return v


# ================= МОДЕЛИ =================
class Question(BaseModel):
    question: str
    user_role: str = "student"
    user_name: str = ""
    student_number: Optional[str] = None
    entity_id: Optional[int] = None


# ================= ЭНДПОИНТЫ =================
@app.post("/api/ask")
async def ask(data: Question, request: Request):
    ip = request.client.host if request.client else "unknown"
    logger.info("Question from %s (role=%s): %s", ip, data.user_role, data.question[:100])

    # Контекст пользователя для персонализации
    user_ctx = "Role: " + data.user_role + ", User: " + (data.user_name or "")
    if data.student_number:
        user_ctx += " (student_id_number='" + data.student_number + "', students.id=" + str(data.entity_id) + ")"

    try:
        t0 = time.time()
        resp = await asyncio.to_thread(
            client.chat.completions.create,
            model=MODEL_URI,
            temperature=0.1,
            max_tokens=2000,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_ctx + "\nQuestion: " + data.question},
            ],
        )
        text = resp.choices[0].message.content
        logger.info("LLM answered in %.2f sec, length=%d", time.time() - t0, len(text))
    except Exception as e:
        logger.error("LLM error: %s", str(e)[:300])
        return JSONResponse({"status": "error",
                             "answer": "Ошибка LLM: " + str(e)[:200],
                             "sql": None, "data": {"columns": [], "rows": []}})

    text = fix_encoding(text)
    raw_sql = extract_sql(text)
    
    if not raw_sql:
        logger.warning("No SQL found in LLM response")
        return JSONResponse({"status": "ok", "answer": text, "sql": None,
                             "data": {"columns": [], "rows": []}})
    
    ok, msg, safe_sql = validate_sql(raw_sql)
    if not ok:
        logger.warning("BLOCKED: %s | SQL: %s", msg, raw_sql[:200])
        return JSONResponse({"status": "blocked", 
                             "answer": "Запрос отклонён системой безопасности: " + msg,
                             "sql": raw_sql, "data": {"columns": [], "rows": []}})

    db_error = None
    try:
        cols, rows = await asyncio.to_thread(run_db, safe_sql)
    except psycopg.errors.QueryCanceled:
        logger.error("Query timeout")
        return JSONResponse({"status": "error",
                             "answer": f"Запрос превысил таймаут {TIMEOUT_SEC} сек.",
                             "sql": safe_sql, "data": {"columns": [], "rows": []}})
    except Exception as e:
        db_error = str(e)[:300]
        logger.error("DB error: %s", db_error)
        cols, rows = [], []

    if db_error:
        logger.info("Retrying with fix prompt")
        try:
            fix_resp = await asyncio.to_thread(
                client.chat.completions.create,
                model=MODEL_URI,
                temperature=0.1,
                max_tokens=2000,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_ctx + "\nQuestion: " + data.question + 
                     "\n\nGenerated SQL:\n" + safe_sql + 
                     "\n\nDatabase error: " + db_error + 
                     "\n\nPlease fix the SQL query."},
                ],
            )
            fix_text = fix_resp.choices[0].message.content
            fix_sql = extract_sql(fix_text)
            
            if fix_sql:
                ok2, msg2, safe_sql2 = validate_sql(fix_sql)
                if ok2:
                    try:
                        cols, rows = await asyncio.to_thread(run_db, safe_sql2)
                        safe_sql = safe_sql2
                        text = fix_text
                        db_error = None
                    except Exception as e2:
                        logger.error("Retry DB error: %s", str(e2)[:300])
        except Exception as e:
            logger.error("Retry LLM error: %s", str(e)[:300])
        
        if db_error:
            return JSONResponse({"status": "error",
                                 "answer": "Ошибка базы данных. Переформулируйте вопрос.",
                                 "sql": safe_sql, "data": {"columns": [], "rows": []}})

    rows = [{k: clean_value(v) for k, v in r.items()} for r in rows]
    logger.info("Success: %d rows", len(rows))

    warning = None
    if len(rows) >= MAX_ROWS:
        warning = f"Результат ограничен {MAX_ROWS} строками. Уточните фильтры."
    elif len(rows) >= LARGE_THRESHOLD:
        warning = f"Результат содержит {len(rows)} строк. Рекомендуем добавить фильтры."

    display = re.sub(r"<sql>.*?</sql>", "", text, flags=re.S)
    display = re.sub(r"```sql.*?```", "", display, flags=re.S)
    display = display.strip()

    return JSONResponse({
        "status": "ok",
        "answer": display,
        "sql": safe_sql,
        "warning": warning,
        "data": {"columns": cols, "rows": rows}
    })


# ================= АНАЛИТИКА =================
@app.get("/api/stats")
async def stats():
    logger.info("Stats requested")

    questions = []
    roles = {}
    blocked = 0
    errors = 0
    total_success = 0

    try:
        with open("app.log", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except FileNotFoundError:
        lines = []

    for line in lines:
        if "Question from" in line:
            m = re.search(r"\(role=(\w+)\):\s*(.+)$", line.strip())
            if m:
                role, q = m.group(1), m.group(2).strip()
                questions.append(q)
                roles[role] = roles.get(role, 0) + 1
        if "BLOCKED:" in line:
            blocked += 1
        if "| ERROR |" in line:
            errors += 1
        if "Success:" in line:
            total_success += 1

    recent = questions[-50:]

    ai_analysis = None
    if recent:
        prompt_questions = "\n".join("- " + q for q in recent)
        try:
            resp = await asyncio.to_thread(
                client.chat.completions.create,
                model=MODEL_URI,
                temperature=0.2,
                max_tokens=800,
                messages=[
                    {"role": "system",
                     "content": "Ты — аналитик университета. Проанализируй список вопросов "
                                "пользователей к AI-ассистенту и выдели 3 главные темы, которые их "
                                "волнуют. Ответь кратко, нумерованным списком на русском языке."},
                    {"role": "user",
                     "content": "Вопросы пользователей:\n" + prompt_questions +
                                "\n\nВыдели 3 главные темы."},
                ],
            )
            ai_analysis = fix_encoding(resp.choices[0].message.content)
        except Exception as e:
            logger.error("Stats LLM error: %s", str(e)[:300])
            ai_analysis = "Аналитика временно недоступна."
    else:
        ai_analysis = "Пока недостаточно данных — задайте несколько вопросов в чате."

    return JSONResponse({
        "status": "ok",
        "total_questions": len(questions),
        "successful_queries": total_success,
        "analyzed_recent": len(recent),
        "roles": roles,
        "blocked_queries": blocked,
        "errors": errors,
        "recent_questions": recent[-10:],
        "ai_analysis": ai_analysis,
    })


# ================= АВТОРИЗАЦИЯ =================
class LoginRequest(BaseModel):
    login: str
    password: str

DEMO_USERS = {
    "ivanov": {
        "password": "stud2026",
        "role": "student",
        "name": "Иванов Иван",
        "entity_id": 1,
        "student_number": "ST-00001"
    },
    "petrova": {
        "password": "teach2026",
        "role": "teacher",
        "name": "Петрова Анна Сергеевна",
        "entity_id": 1,
        "student_number": None
    },
    "admin": {
        "password": "admin2026",
        "role": "admin",
        "name": "Управление аналитики",
        "entity_id": 1,
        "student_number": None
    }
}


@app.post("/api/auth")
async def auth(data: LoginRequest):
    user = DEMO_USERS.get(data.login)
    if not user or user["password"] != data.password:
        return JSONResponse(
            status_code=401,
            content={"success": False, "detail": "Неверный логин или пароль"}
        )
    
    return JSONResponse({
        "success": True,
        "role": user["role"],
        "name": user["name"],
        "entity_id": user["entity_id"],
        "student_number": user["student_number"]
    })


@app.get("/health")
async def health():
    return {"status": "ok", "time": datetime.now().isoformat()}


@app.get("/widget.js")
async def widget_js():
    return FileResponse("static/widget.js", media_type="text/javascript")


@app.get("/")
async def index():
    try:
        with open("static/index.html", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    except FileNotFoundError:
        return HTMLResponse("<h1>Положите файл static/index.html в папку со скриптом</h1>", status_code=500)


os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)