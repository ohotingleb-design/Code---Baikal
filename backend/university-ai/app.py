import asyncio
import logging
import re
import time
from decimal import Decimal
from datetime import datetime, date

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import psycopg
from psycopg.rows import dict_row
from openai import OpenAI

# ================= НАСТРОЙКИ =================
# ⚠️ 1. Впишите сюда свой API-ключ Yandex Cloud
YANDEX_API_KEY = "AQVN3awuGYT3gVtFGwyg3bTjsy77sfriDgnFxM_W"  # <-- ЗАМЕНИТЕ!

# ⚠️ 2. Впишите сюда свой FOLDER_ID из Yandex Cloud
FOLDER_ID = "b1gq8ef571dtt80m92rs"  # <-- ЗАМЕНИТЕ!
MODEL_URI = f"gpt://{FOLDER_ID}/yandexgpt-lite/latest"

# ⚠️ 3. Впишите сюда свои данные от PostgreSQL
DB_HOST = "127.0.0.1"
DB_PORT = 5432
DB_NAME = "university_db"
DB_USER = "db11_user"
DB_PASSWORD = "12345"

MAX_ROWS = 50
TIMEOUT_SEC = 5
LARGE_THRESHOLD = 20

logging.basicConfig(filename="app.log", level=logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(message)s",
                    encoding="utf-8")
logger = logging.getLogger("uni-ai")

# Актуальный URL для OpenAI-совместимого API Yandex Cloud AI Studio
client = OpenAI(base_url="https://ai.api.cloud.yandex.net/v1", api_key=YANDEX_API_KEY)
app = FastAPI(title="University AI Assistant - Kod Baikala")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

# ================= SYSTEM PROMPT =================
SYSTEM_PROMPT = """Ты — AI-ассистент университета для хакатона "Код Байкала".
Преобразуй вопросы на русском языке в безопасные SQL-запросы к PostgreSQL.

СХЕМА БАЗЫ ДАННЫХ:
faculties(id, name) — факультеты
departments(id, faculty_id, name) — кафедры
programs(id, name, budget_places, paid_places) — направления подготовки
staff(id, full_name, position, department_id) — сотрудники (ФИО разрешены)
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
students.faculty_id = faculties.id
applicants.program_id = programs.id
departments.faculty_id = faculties.id

БЕЗОПАСНОСТЬ (КРИТИЧНО!):
1. ТОЛЬКО SELECT (или WITH ... SELECT). INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE — вежливый отказ без SQL.
2. ЗАПРЕЩЕНО выводить: student_id_number, ФИО студентов, ФИО абитуриентов, списки конкретных студентов.
3. Данные студентов/абитуриентов — ТОЛЬКО через агрегаты COUNT/AVG/SUM/MIN/MAX + GROUP BY.
4. РАЗРЕШЕНО выводить ФИО: teachers.full_name, staff.full_name, admins.full_name.
5. НЕ выдумывай данные и таблицы.
6. При поиске по конкретным названиям или именам используй ILIKE с подстрокой: ILIKE '%слово%'. Для общих запросов (например, "покажи все факультеты") используй обычный SELECT без WHERE.
7. Для агрегатов (COUNT, AVG, SUM) БЕЗ GROUP BY НЕ добавляй LIMIT.
8. Для сырых списков строк или агрегатов с GROUP BY добавляй LIMIT 50.

РОЛИ ПОЛЬЗОВАТЕЛЕЙ:
- Абитуриент: направления, бюджет/платные места, проходной балл (AVG total_score WHERE is_admitted=true).
- Студент: свои оценки, средний балл, задолженности (is_passed=false).
- Преподаватель: свои дисциплины, количество студентов, средний балл.
- Декан/администрация: численность по факультетам, динамика набора (обезличенно).

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
Если вопрос не про данные БД (приветствие, общие вопросы) — всё равно сгенерируй простой SQL типа SELECT 'Привет! Я готов помочь.' AS answer.
"""

WHITELIST = {"faculties", "departments", "programs", "staff", "teachers",
             "students", "applicants", "courses", "grades", "admins"}
FORBIDDEN = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
             "CREATE", "GRANT", "EXEC", "COPY", "PG_SLEEP", "SLEEP",
             "XP_", "SHUTDOWN", "INTO OUTFILE", "INTO DUMPFILE"]


def fix_encoding(text):
    """Исправляет кракозябры UTF-8-как-CP1251 (типично для Windows+httpx)"""
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
    """Извлекает SQL из ответа LLM, безопасно очищая от markdown-оберток"""
    # 1. Ищем внутри тегов <sql>
    m = re.search(r"<sql>\s*(.*?)\s*</sql>", text, re.S | re.I)
    if m:
        sql = m.group(1).strip()
        # Удаляем возможные markdown-обертки, если нейросеть вставила их внутрь тега
        sql = re.sub(r"^```sql\s*", "", sql, flags=re.I)
        sql = re.sub(r"\s*```$", "", sql, flags=re.I)
        return sql.strip()
    
    # 2. Ищем просто markdown блок
    m = re.search(r"```sql\s*(.*?)\s*```", text, re.S | re.I)
    if m:
        return m.group(1).strip()
    
    # 3. Ищем SELECT с начала строки или после переноса
    m = re.search(r"(SELECT\b.*?)(?:\n\n|\Z)", text, re.S | re.I)
    if m:
        sql = m.group(1).strip()
        if (sql.startswith('"') and sql.endswith('"')) or \
           (sql.startswith("'") and sql.endswith("'")):
            inner = sql[1:-1]
            if "'" not in inner and '"' not in inner:
                sql = inner
        return sql
    
    return None


def validate_sql(sql):
    """Проверяет SQL на безопасность. Возвращает (ok, message, cleaned_sql)"""
    if not sql:
        return False, "Empty SQL", None
    
    s = str(sql).strip().rstrip(";").strip()
    up = s.upper()
    
    # РАЗРЕШАЕМ и SELECT, и WITH (для CTE - сложных аналитических запросов)
    if not (up.lstrip().startswith("SELECT") or up.lstrip().startswith("WITH")):
        return False, "Only SELECT or WITH (CTE) allowed", None
    
    for kw in FORBIDDEN:
        if re.search(r"\b" + kw + r"\b", up):
            return False, "Forbidden keyword: " + kw, None
    
    if re.search(r"\bUNION\b.*\b(INSERT|UPDATE|DELETE|DROP)\b", up):
        return False, "UNION with modification queries forbidden", None
    
    if "--" in s or "/*" in s or ";" in s:
        return False, "Comments and compound queries forbidden", None
    
    # Улучшенный regex: учитывает кавычки и корректно извлекает имена таблиц
    tables = {t.lower().strip('"') for t in re.findall(r"(?:FROM|JOIN)\s+\"?([a-zA-Z_]\w*)\"?", s)}
    bad = tables - WHITELIST
    if bad:
        return False, "Tables outside whitelist: " + ", ".join(sorted(bad)), None
    
    has_agg = any(f in up for f in ("COUNT(", "AVG(", "SUM(", "MIN(", "MAX("))
    has_group = "GROUP BY" in up
    
    # Добавляем LIMIT, если его нет и это не чистый агрегат без группировки
    if "LIMIT" not in up and not has_agg:
        s += " LIMIT " + str(MAX_ROWS)
    elif "LIMIT" not in up and has_agg and has_group:
        s += " LIMIT " + str(MAX_ROWS)
    
    return True, "ok", s


def run_db(sql):
    """Выполняет SQL-запрос в базе данных"""
    if isinstance(sql, bytes):
        sql = sql.decode('utf-8', errors='replace')
    
    # Очистка от невидимых управляющих символов
    cleaned = []
    for c in sql:
        code = ord(c)
        if c in '\n\t' or (code >= 32 and code != 127 and code != 0xFEFF):
            cleaned.append(c)
    sql = ''.join(cleaned)
    
    logger.info("Executing SQL: %s", sql[:300])
    
    conn = psycopg.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        row_factory=dict_row
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
    """Приводит значения к JSON-сериализуемым типам"""
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if v is None:
        return None
    return v


class Question(BaseModel):
    question: str
    user_role: str = "student"


@app.post("/api/ask")
async def ask(data: Question, request: Request):
    ip = request.client.host if request.client else "unknown"
    logger.info("Question from %s (role=%s): %s", ip, data.user_role, data.question[:100])

    try:
        t0 = time.time()
        resp = await asyncio.to_thread(
            client.chat.completions.create,
            model=MODEL_URI,
            temperature=0.1,
            max_tokens=2000,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": "Role: " + data.user_role + "\nQuestion: " + data.question},
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

    try:
        cols, rows = await asyncio.to_thread(run_db, safe_sql)
    except psycopg.errors.QueryCanceled:
        logger.error("Query timeout")
        return JSONResponse({"status": "error",
                             "answer": f"Запрос превысил таймаут {TIMEOUT_SEC} сек. Пожалуйста, уточните фильтры (год, факультет).",
                             "sql": safe_sql, "data": {"columns": [], "rows": []}})
    except Exception as e:
        logger.error("DB error: %s", str(e)[:300])
        return JSONResponse({"status": "error",
                             "answer": "Ошибка базы данных. Переформулируйте вопрос или проверьте схему.",
                             "sql": safe_sql, "data": {"columns": [], "rows": []}})

    rows = [{k: clean_value(v) for k, v in r.items()} for r in rows]
    logger.info("Success: %d rows", len(rows))

    warning = None
    if len(rows) >= MAX_ROWS:
        warning = f"Результат ограничен {MAX_ROWS} строками. Уточните фильтры: год, факультет, семестр, статус."
    elif len(rows) >= LARGE_THRESHOLD:
        warning = f"Результат содержит {len(rows)} строк. Рекомендуем добавить фильтры для уточнения."

    # Очищаем вывод от SQL-блоков для красивого отображения в чате
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


@app.get("/health")
async def health():
    return {"status": "ok", "time": datetime.now().isoformat()}


@app.get("/")
async def index():
    try:
        with open("static/index.html", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    except FileNotFoundError:
        return HTMLResponse("<h1>Положите файл static/index.html в папку со скриптом</h1>", status_code=500)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)