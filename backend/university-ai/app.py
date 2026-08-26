import asyncio
import logging
import re
import time
import os
import json
from decimal import Decimal
from datetime import datetime, date
from pathlib import Path

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

# ================= НАСТРОЙКИ =================
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

# ================= ЛОГИРОВАНИЕ =================
BASE_DIR = Path(__file__).parent.resolve()
LOG_FILE_PATH = BASE_DIR / "app.log"

logging.basicConfig(
    filename=str(LOG_FILE_PATH),
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    encoding="utf-8",
    force=True 
)
logger = logging.getLogger("uni-ai")
logger.info(f"=== СЕРВЕР ЗАПУЩЕН. Логи: {LOG_FILE_PATH} ===")

# ================= ЗАГРУЗКА РЕАЛЬНОЙ СХЕМЫ БД =================
def get_real_schema():
    """Загружает реальную схему БД из information_schema"""
    try:
        conn = psycopg.connect(
            host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
            user=DB_USER, password=DB_PASSWORD, row_factory=dict_row
        )
        cur = conn.cursor()
        
        # Получаем все таблицы из public schema
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
        """)
        tables = [row['table_name'] for row in cur.fetchall()]
        
        # Получаем колонки для каждой таблицы
        schema = {}
        for table in tables:
            cur.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = %s
                ORDER BY ordinal_position
            """, (table,))
            schema[table] = [(row['column_name'], row['data_type']) for row in cur.fetchall()]
        
        conn.close()
        logger.info("Loaded real DB schema: %d tables", len(schema))
        return schema
    except Exception as e:
        logger.error("Failed to load DB schema: %s", str(e)[:200])
        return None

# Загружаем схему при старте
REAL_SCHEMA = get_real_schema()
if REAL_SCHEMA:
    REAL_TABLES = set(REAL_SCHEMA.keys())
    logger.info("Real tables in DB: %s", ", ".join(sorted(REAL_TABLES)))
else:
    REAL_TABLES = None  # Будем полагаться только на WHITELIST

# ================= ИНИЦИАЛИЗАЦИЯ =================
client = OpenAI(
    api_key=YANDEX_API_KEY,
    base_url="https://ai.api.cloud.yandex.net/v1"
)
app = FastAPI(title="University AI Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================= SYSTEM PROMPT =================
SYSTEM_PROMPT = """Ты — AI-ассистент университета. Превращай вопросы на русском в безопасные SQL-запросы к PostgreSQL.

═══════ СХЕМА БД (ТОЛЬКО ЭТИ ТАБЛИЦЫ СУЩЕСТВУЮТ!) ═══════
faculties(id, name), departments(id, faculty_id, name), programs(id, faculty_id, name, budget_places, paid_places),
teachers(id, full_name, department_id), students(id, student_id_number, group_name, faculty_id, enrollment_year),
applicants(id, application_year, program_id, total_score INTEGER — СУММА баллов ЕГЭ, is_admitted BOOLEAN),
courses(id, name, teacher_id, semester TEXT: 'осенний'/'весенний'),
grades(id, student_id, course_id, grade, is_passed BOOLEAN), admins(id, full_name, position).

⚠️ В БАЗЕ НЕТ: аудиторий, расписания, корпусов, контактов, баллов ЕГЭ по отдельным предметам.

⚠️ КРИТИЧЕСКИ ВАЖНО — АНТИ-ГАЛЛЮЦИНАЦИИ:
• Генерируй SQL ТОЛЬКО к таблицам из списка выше: faculties, departments, programs, teachers, students, applicants, courses, grades, admins.
• Если вопрос про данные, которых НЕТ в схеме (аудитории, расписание, корпуса, контакты) — ОБЯЗАТЕЛЬНО верни:
  <sql>SELECT 'no_data' AS result</sql>
  И напиши, что такой информации нет в базе.
• ЗАПРЕЩЕНО выдумывать названия таблиц или колонок!
• Если сомневаешься — используй SELECT 'no_data' AS result.

═══════ БЕЗОПАСНОСТЬ ═══════
• ТОЛЬКО SELECT (или WITH ... SELECT). INSERT/UPDATE/DELETE/DROP — вежливый отказ.
• ЗАПРЕЩЕНО: student_id_number, ФИО студентов/абитуриентов, списки конкретных студентов.
• Данные студентов/абитуриентов — ТОЛЬКО агрегаты (COUNT/AVG/SUM) + GROUP BY.
• РАЗРЕШЕНО ФИО: teachers.full_name, admins.full_name.
• Поиск: ILIKE '%слово%'. Апостроф: Д''Артаньян. %: 100\%%.
• application_year, enrollment_year — INTEGER (2021, 2022). НЕ используй EXTRACT/YEAR.
• Агрегаты БЕЗ GROUP BY — без LIMIT. С GROUP BY или списки — LIMIT 50.
❗ ЗАПРЕТ ИНТРОСПЕКЦИИ (КРИТИЧНО!):
• НИКОГДА не запрашивай information_schema, pg_catalog, pg_class, pg_attribute, pg_tables и системные таблицы.
• Если просят "покажи структуру таблицы", "типы колонок", "oid", "внутренние идентификаторы" — НЕ генерируй SQL для интроспекции.
• Верни:
  <sql>SELECT 'blocked' AS result</sql>
  И напиши: "По соображениям безопасности я не раскрываю внутреннюю структуру базы данных (типы колонок, oid, системные таблицы). Могу ответить на вопросы о данных университета: студенты, преподаватели, направления, оценки."

═══════ СПЕЦИАЛЬНЫЕ ПРАВИЛА ═══════
• total_score = СУММА баллов ЕГЭ. Если просят балл по математике — скажи, что есть только суммарный.
• "Должник" = is_passed = false. "Сдал" = is_passed = true.
• group_name — TEXT ('БИВ-211'). Используй: WHERE group_name ILIKE '%БИВ-211%'.
• semester — TEXT ('осенний' или 'весенний').
• «1-й семестр» = 'осенний', «2-й семестр» = 'весенний'.
• «Текущий семестр» — используй оба: IN ('осенний', 'весенний').
❗ ВОПРОСЫ "КТО ИЗ СТУДЕНТОВ..." / СПИСКИ СТУДЕНТОВ:
По политике безопасности ЗАПРЕЩЕНО выводить списки конкретных студентов.
Если пользователь спрашивает "кто из студентов не сдал экзамен / у кого задолженности" — 
верни АГРЕГАТ (COUNT) или распределение по ГРУППАМ (группы — не персональные данные):
<sql>
SELECT s.group_name, COUNT(DISTINCT s.id) AS students_with_debts
FROM students s
JOIN grades g ON g.student_id = s.id
WHERE g.is_passed = false
GROUP BY s.group_name
ORDER BY students_with_debts DESC
LIMIT 10
</sql>
И объясни: "По политике безопасности я не могу выводить списки конкретных студентов, 
но могу сообщить, что N студентов имеют задолженности. Больше всего должников в группах X и Y."
❗ ПРАВИЛА ДЛЯ "ПЛАТНИКОВ / БЮДЖЕТНИКОВ":
В базе НЕТ признака платник/бюджетник у отдельных студентов.
Долю платников считай ТОЛЬКО из мест в таблице programs:
paid_places / (budget_places + paid_places).
ОБЯЗАТЕЛЬНО защищайся от деления на ноль через NULLIF(..., 0).
"Не показывай направления без платников" = WHERE p.paid_places > 0.

Пример:
<sql>
SELECT p.name AS program,
       ROUND(100.0 * p.paid_places / NULLIF(p.budget_places + p.paid_places, 0)) AS paid_percentage
FROM programs p
WHERE p.paid_places > 0
ORDER BY paid_percentage DESC
LIMIT 50
</sql>
Наибольшая доля платников на направлении "Экономика" — 50%. Направления без платников скрыты.

❗ ПРАВИЛА ДЛЯ ПОИСКА НАПРАВЛЕНИЙ ПРОГРАММ:
Если пользователь спрашивает про направление (например, "Информатика"), используй ILIKE '%Информатика%'.
ОБЯЗАТЕЛЬНО используй GROUP BY p.name и агрегатную функцию SUM(p.budget_places), чтобы корректно показать общее количество мест, если в базе есть несколько направлений с похожим названием.
Пример:
<sql>
SELECT p.name, SUM(p.budget_places) AS total_budget
FROM programs p
WHERE p.name ILIKE '%Информатика%'
GROUP BY p.name
ORDER BY total_budget DESC
</sql>

❗ ДУБЛИКАТЫ НАПРАВЛЕНИЙ:
В таблице programs могут быть несколько записей с одинаковым названием (разные коды/профили).
Если пользователь спрашивает про направление (например, "Информатика"), ОБЯЗАТЕЛЬНО используй GROUP BY и SUM:
<sql>
SELECT name, 
       SUM(budget_places) AS total_budget,
       SUM(paid_places) AS total_paid
FROM programs
WHERE name ILIKE '%Информатика%'
GROUP BY name
</sql>
Это покажет суммарные места по всем профилям направления.

═══════ ПЕРСОНАЛИЗАЦИЯ ═══════
• Если авторизован (student_id=X) и спрашивает "мои оценки/балл/долги" — ОБЯЗАТЕЛЬНО WHERE grades.student_id = X.
• Если НЕ авторизован и просит "мои оценки" — попроси войти.

═══════ ФОРМАТ ОТВЕТА ═══════
1. SQL в тегах <sql>...</sql>
2. Сразу после </sql> — короткий естественный ответ (1-3 предложения).
3. НЕ пиши "ОБЪЯСНЕНИЕ", "ОТВЕТ". Просто ответ как в чате.
4. Используй ТОЛЬКО реальные данные из БД.

ПРИМЕРЫ:
<sql>SELECT COUNT(*) FROM students</sql>
В университете обучается 5000 студентов.

Вопрос: "Выведи топ-3 преподавателей с наибольшим количеством студентов во 2-м семестре"
<sql>
SELECT t.full_name, COUNT(DISTINCT g.student_id) AS student_count
FROM teachers t
JOIN courses c ON c.teacher_id = t.id
JOIN grades g ON g.course_id = c.id
WHERE c.semester = 'весенний'
GROUP BY t.id, t.full_name
ORDER BY student_count DESC
LIMIT 3
</sql>
Больше всего студентов во 2-м семестре у Петровой А.С. — 120 человек, у Иванова П.И. — 95, у Сидоровой М.П. — 80.

Вопрос: "Кто из студентов не сдал ни одного экзамена?"
<sql>
SELECT s.group_name, COUNT(DISTINCT s.id) AS students_with_debts
FROM students s
JOIN grades g ON g.student_id = s.id
WHERE g.is_passed = false
GROUP BY s.group_name
ORDER BY students_with_debts DESC
LIMIT 10
</sql>
По политике безопасности я не могу выводить списки конкретных студентов, но могу сообщить, 
что 45 студентов имеют хотя бы одну задолженность. Больше всего должников в группах БИВ-211 (12 человек) и ИВТ-102 (9 человек).

<sql>SELECT 'no_data' AS result</sql>
К сожалению, в базе нет информации об аудиториях и расписании.

Если вопрос не про БД — SQL: SELECT 'Привет!' AS answer, потом приветствие.
"""

WHITELIST = {"faculties", "departments", "programs", "teachers",
             "students", "applicants", "courses", "grades", "admins"}
FORBIDDEN = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
             "CREATE", "GRANT", "EXEC", "COPY", "PG_SLEEP", "SLEEP",
             "XP_", "SHUTDOWN", "INTO OUTFILE", "INTO DUMPFILE",
             "INFORMATION_SCHEMA", "PG_CATALOG", "PG_CLASS", "PG_ATTRIBUTE",
             "PG_TABLES", "OID"]


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
    
    # Проверка 1: Whitelist
    bad = tables - WHITELIST - cte_names
    if bad:
        return False, "Tables outside whitelist: " + ", ".join(sorted(bad)), None
    
    # Проверка 2: Реальное существование таблиц в БД (анти-галлюцинации)
    if REAL_TABLES:
        bad_real = tables - REAL_TABLES - cte_names
        if bad_real:
            return False, "Tables do not exist in database: " + ", ".join(sorted(bad_real)), None
    
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

    user_ctx = "Role: " + data.user_role + ", User: " + (data.user_name or "")
    if data.student_number:
        user_ctx += " (student_id_number='" + data.student_number + "', students.id=" + str(data.entity_id) + ")"

    # ===== ЭТАП 1: Генерация SQL =====
    try:
        resp = await asyncio.to_thread(
            client.chat.completions.create,
            model=MODEL_URI, temperature=0.1, max_tokens=2000,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_ctx + "\nQuestion: " + data.question},
            ],
        )
        text = resp.choices[0].message.content
    except Exception as e:
        logger.error("LLM error: %s", str(e)[:300])
        return JSONResponse({"status": "error", "answer": "Ошибка LLM: " + str(e)[:200],
                             "sql": None, "data": {"columns": [], "rows": []}})

    text = fix_encoding(text)
    raw_sql = extract_sql(text)
    
    if not raw_sql:
        return JSONResponse({"status": "ok", "answer": text, "sql": None, "data": {"columns": [], "rows": []}})
    
    ok, msg, safe_sql = validate_sql(raw_sql)
    if not ok:
        logger.warning("BLOCKED: %s | SQL: %s", msg, raw_sql[:200])
        return JSONResponse({"status": "blocked", "answer": "Запрос отклонён системой безопасности: " + msg,
                             "sql": None, "data": {"columns": [], "rows": []}})

    # ===== Выполнение SQL =====
    db_error = None
    try:
        cols, rows = await asyncio.to_thread(run_db, safe_sql)
    except psycopg.errors.QueryCanceled:
        logger.error("Query timeout")
        return JSONResponse({"status": "error", "answer": f"Запрос превысил таймаут {TIMEOUT_SEC} сек.",
                             "sql": None, "data": {"columns": [], "rows": []}})
    except Exception as e:
        db_error = str(e)
        logger.error("DB error: %s", db_error[:300])
        cols, rows = [], []

    # ===== Self-healing =====
    if db_error:
        logger.info("Retrying with fix prompt")
        try:
            fix_resp = await asyncio.to_thread(
                client.chat.completions.create, model=MODEL_URI, temperature=0.1, max_tokens=2000,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_ctx + "\nQuestion: " + data.question + 
                     "\n\nGenerated SQL:\n" + safe_sql + 
                     "\n\nDatabase error: " + db_error + "\n\nPlease fix the SQL query."},
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
                        db_error = str(e2)
        except Exception as e:
            logger.error("Retry LLM error: %s", str(e)[:300])
        
            # Несуществующие таблицы/колонки
            if "does not exist" in error_lower or "relation" in error_lower or "column" in error_lower:
                logger.warning("LLM hallucinated non-existent table/column")
                return JSONResponse({
                    "status": "ok",
                    "answer": "К сожалению, в базе данных нет информации по этому вопросу. Я могу помочь с вопросами про студентов, преподавателей, абитуриентов, направления подготовки и оценки.",
                    "sql": None, "data": {"columns": [], "rows": []}
                })
            
            # Деление на ноль и прочие арифметические ошибки
            if "division by zero" in error_lower or "numeric field overflow" in error_lower:
                logger.warning("Arithmetic error in generated SQL")
                return JSONResponse({
                    "status": "ok",
                    "answer": "Не удалось корректно посчитать показатель — в данных есть направления с нулевыми местами. Попробуйте уточнить вопрос, например: «доля платников по направлениям, где есть платные места».",
                    "sql": None, "data": {"columns": [], "rows": []}
                })
            
            return JSONResponse({
                "status": "error", "answer": "Не удалось выполнить запрос. Попробуйте переформулировать вопрос.",
                "sql": None, "data": {"columns": [], "rows": []}
            })

    rows = [{k: clean_value(v) for k, v in r.items()} for r in rows]
    logger.info("Success: %d rows", len(rows))

    # ===== Определяем тип ответа =====
    is_service = (
        "'no_data'" in (safe_sql or "").lower() or
        "'blocked'" in (safe_sql or "").lower() or
        "'привет'" in (safe_sql or "").lower() or
        (len(rows) == 1 and str(rows[0].get('result', '')).lower() in ['no_data', 'blocked', 'привет'])
    )
    
    # Успешный запрос (не служебный и не простое приветствие)
    is_successful_query = not is_service and not (len(rows) == 1 and len(cols) == 1 and cols[0] == 'answer')
    
    # Есть ли реальные данные для отображения в таблице
    has_real_data = is_successful_query and len(rows) > 0

    # ===== ЭТАП 2: Генерация естественного ответа =====
    display = ""
    
    if is_service:
        display = re.sub(r"^.*?</sql>\s*", "", text, flags=re.S | re.I).strip()
        if not display:
            display = re.sub(r"<sql>.*?</sql>", "", text, flags=re.S).strip()
    elif is_successful_query:
        # Вызываем LLM даже при пустом результате (len(rows) == 0)
        try:
            data_preview = rows[:15] if len(rows) > 15 else rows
            data_str = json.dumps(data_preview, ensure_ascii=False, indent=2) if data_preview else "[]"
            
            # ВАЖНО: явно сообщаем LLM о количестве строк
            data_context = f"ДАННЫЕ ИЗ БД ({len(rows)} строк):"
            if len(rows) == 0:
                data_context += "\n[ПУСТОЙ РЕЗУЛЬТАТ — запрос выполнен, но ничего не найдено]"
            else:
                data_context += f"\n(первые {len(data_preview)} из {len(rows)}):\n{data_str}"
            
            answer_prompt = f"""На основе вопроса и результата запроса к БД, сгенерируй короткий естественный ответ на русском.

ВОПРОС: {data.question}

{data_context}

ТРЕБОВАНИЯ:
- Если результат ПУСТОЙ (0 строк) — скажи, что по запросу ничего не найдено (например: "Все преподаватели ведут хотя бы одну дисциплину" или "Студентов с задолженностями не найдено")
- Используй ТОЛЬКО реальные данные, не придумывай
- Ответ: 1-3 предложения, как в обычном чате
- НЕ пиши SQL, "ОТВЕТ:", просто дай финальный текст
- Если в данных есть агрегаты (COUNT, SUM) со значением > 0 — НЕ говори "ничего не найдено", используй эти числа в ответе
- Если вопрос про "кто из студентов" — объясни, что списки студентов защищены политикой безопасности, и приведи агрегаты/группы

ОТВЕТ:"""
            
            answer_resp = await asyncio.to_thread(
                client.chat.completions.create, model=MODEL_URI, temperature=0.3, max_tokens=500,
                messages=[
                    {"role": "system", "content": "Дружелюбный AI-ассистент. Отвечай кратко, используя реальные данные."},
                    {"role": "user", "content": answer_prompt},
                ],
            )
            display = answer_resp.choices[0].message.content.strip()
        except Exception as e:
            logger.error("Answer generation error: %s", str(e)[:200])
            display = re.sub(r"^.*?</sql>\s*", "", text, flags=re.S | re.I).strip()
            if not display:
                display = "По вашему запросу данные не найдены."
    else:
        display = re.sub(r"<sql>.*?</sql>", "", text, flags=re.S).strip() or text.strip()
    
    if not display:
        display = "По вашему запросу данные не найдены."

    # ===== Финальный ответ =====
    warning = None
    if has_real_data:
        if len(rows) >= MAX_ROWS:
            warning = f"Результат ограничен {MAX_ROWS} строками."
        elif len(rows) >= LARGE_THRESHOLD:
            warning = f"Результат содержит {len(rows)} строк."

    return JSONResponse({
        "status": "ok",
        "answer": display,
        "sql": None,
        "warning": warning,
        "data": {"columns": cols, "rows": rows} if has_real_data else {"columns": [], "rows": []}
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
        with open(LOG_FILE_PATH, encoding="utf-8", errors="replace") as f:
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
                     "content": "Ты — аналитик университета. Проанализируй список вопросов и выдели 3 главные темы. Ответь кратко на русском."},
                    {"role": "user",
                     "content": "Вопросы:\n" + prompt_questions},
                ],
            )
            ai_analysis = fix_encoding(resp.choices[0].message.content)
        except Exception as e:
            logger.error("Stats LLM error: %s", str(e)[:300])
            ai_analysis = "Аналитика временно недоступна."
    else:
        ai_analysis = "Недостаточно данных."

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


# ================= ЛОГИ =================
class LogRequest(BaseModel):
    lines: int = 100
    filter: str = ""
    user_role: str = "applicant"

@app.post("/api/logs")
async def get_logs(data: LogRequest):
    if data.user_role != "admin":
        return JSONResponse(status_code=403, content={"success": False, "detail": "Доступ запрещен."})

    all_lines = []
    
    try:
        with open(LOG_FILE_PATH, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
    except FileNotFoundError:
        return JSONResponse({
            "success": True, 
            "lines": [f"Файл не найден: {LOG_FILE_PATH}"],
            "stats": {"total_lines": 0, "questions": 0, "errors": 0, "blocked": 0}
        })

    total_lines = len(all_lines)
    questions = sum(1 for line in all_lines if "Question from" in line)
    errors = sum(1 for line in all_lines if "ERROR" in line or "error" in line)
    blocked = sum(1 for line in all_lines if "BLOCKED:" in line)

    if data.filter:
        filtered_lines = [line.strip() for line in all_lines if data.filter.lower() in line.lower()]
    else:
        filtered_lines = [line.strip() for line in all_lines]

    recent_lines = filtered_lines[-data.lines:]
    recent_lines.reverse()

    return JSONResponse({
        "success": True,
        "lines": recent_lines,
        "stats": {
            "total_lines": total_lines,
            "questions": questions,
            "errors": errors,
            "blocked": blocked
        }
    })


# ================= АВТОРИЗАЦИЯ =================
class LoginRequest(BaseModel):
    login: str
    password: str

DEMO_USERS = {
    "ivanov": {"password": "stud2026", "role": "student", "name": "Иванов Иван", "entity_id": 1, "student_number": "ST-00001"},
    "petrova": {"password": "teach2026", "role": "teacher", "name": "Петрова Анна Сергеевна", "entity_id": 1, "student_number": None},
    "admin": {"password": "admin2026", "role": "admin", "name": "Управление аналитики", "entity_id": 1, "student_number": None}
}


@app.post("/api/auth")
async def auth(data: LoginRequest):
    logger.info(f"Auth attempt: login='{data.login}', password='{data.password}'")
    
    demo_user = DEMO_USERS.get(data.login.lower())
    if demo_user and demo_user["password"] == data.password:
        logger.info(f"Auth success via DEMO_USERS: {data.login}")
        return JSONResponse({
            "success": True,
            "role": demo_user["role"],
            "name": demo_user["name"],
            "entity_id": demo_user["entity_id"],
            "student_number": demo_user["student_number"]
        })
    
    conn = None
    try:
        conn = psycopg.connect(
            host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
            user=DB_USER, password=DB_PASSWORD, row_factory=dict_row
        )
        cur = conn.cursor()
        
        cur.execute("SELECT COUNT(*) as count FROM users")
        total_users = cur.fetchone()
        logger.info(f"Total users in DB: {total_users['count']}")
        
        cur.execute("SELECT login, role, full_name FROM users WHERE login = %s", (data.login,))
        user_no_pass = cur.fetchone()
        if user_no_pass:
            logger.info(f"User found (without password check): {user_no_pass}")
        else:
            logger.warning(f"User NOT found in DB with login: '{data.login}'")
        
        cur.execute("""
            SELECT login, role, full_name, entity_id, student_number 
            FROM users 
            WHERE login = %s AND password = %s
        """, (data.login, data.password))
        
        user = cur.fetchone()
        
        if user:
            logger.info(f"Auth success via DB: {user['login']}")
            return JSONResponse({
                "success": True,
                "role": user["role"],
                "name": user["full_name"],
                "entity_id": user["entity_id"],
                "student_number": user["student_number"]
            })
        else:
            logger.warning(f"User found but password mismatch for: {data.login}")
            
    except Exception as e:
        logger.error(f"Auth DB error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        if conn:
            conn.close()
    
    logger.warning(f"Auth failed for: {data.login}")
    return JSONResponse(
        status_code=401,
        content={"success": False, "detail": "Неверный логин или пароль"}
    )


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
        return HTMLResponse("<h1>Положите файл static/index.html</h1>", status_code=500)


os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/demo")
async def demo_page():
    """Страница демонстрации встраиваемого виджета"""
    try:
        with open("static/demo.html", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    except FileNotFoundError:
        return HTMLResponse("<h1>Файл static/demo.html не найден</h1>", status_code=500)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)