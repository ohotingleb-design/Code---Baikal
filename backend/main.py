"""
ИИ-ассистент университета — единый бэкенд.
Цикл: Вопрос → LLM → SQL → Проверка → Выполнение → Ответ.
Запуск: uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""
import logging
import os
import re
from contextlib import asynccontextmanager

import asyncpg
import sqlparse
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI
from pydantic import BaseModel

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# ============================== НАСТРОЙКИ ==============================
# LLM видит ТОЛЬКО эти таблицы (users/admins скрыты — политика ПДн)
WHITELIST_TABLES = ["faculties", "departments", "programs", "staff",
                    "teachers", "students", "applicants", "courses", "grades"]

llm = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
pool: asyncpg.Pool | None = None

# ============================== БАЗА ДАННЫХ ==============================
async def db_connect():
    global pool
    pool = await asyncpg.create_pool(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", 5432)),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        server_settings={"statement_timeout": "5000", "application_name": "baikal_hackathon"},
    )

async def get_schema() -> str:
    """Схема БД (только whitelist) — передаётся в LLM вместо данных."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name = ANY($1)
            ORDER BY table_name, ordinal_position
            """, WHITELIST_TABLES)
    schema = {}
    for r in rows:
        schema.setdefault(r["table_name"], []).append(f"{r['column_name']} ({r['data_type']})")
    return "".join(f"Table: {t}\nColumns: {', '.join(c)}\n\n" for t, c in schema.items())

# ============================== LLM ==============================
BASE_PROMPT = """
Ты — интеллектуальный ассистент университета (PostgreSQL).
Генерируй ТОЛЬКО валидные SQL SELECT-запросы по вопросу пользователя.
1. Только SELECT; обязательно LIMIT (не более 100), если запрос не агрегатный.
2. Не придумывай данные. Если таблицы нет в схеме — верни: "Ошибка: таблица не найдена".
3. Персональные данные студентов и абитуриентов выводить ЗАПРЕЩЕНО — только агрегаты (COUNT/AVG/SUM) без ФИО.
4. ФИО преподавателей и сотрудников выводить разрешено.

СХЕМА БАЗЫ ДАННЫХ:
{schema}

Верни ТОЛЬКО SQL-код, без markdown и пояснений.
"""

def role_prompt(role, entity_id, student_number):
    if role == "student" and student_number:
        return (f"РОЛЬ: СТУДЕНТ с students.student_id_number='{student_number}'. "
                f"Запросы «мои данные» фильтруй по students.student_id_number='{student_number}' "
                "(JOIN grades/courses). Данные других студентов — только агрегированно.")
    if role == "teacher" and entity_id:
        return (f"РОЛЬ: ПРЕПОДАВАТЕЛЬ с teachers.id={entity_id}. "
                f"«Мои дисциплины» — фильтруй courses.teacher_id={entity_id}. ФИО студентов не выводить.")
    if role == "admin":
        return ("РОЛЬ: СОТРУДНИК/АДМИНИСТРАЦИЯ. Агрегированная отчётность по факультетам, "
                "приёму и нагрузке; статистика отчислений без ФИО.")
    return ("РОЛЬ: АБИТУРИЕНТ. Только публичная агрегированная статистика приёма "
            "(programs, applicants) — без персональных данных.")

async def generate_sql(question, schema, role, entity_id, student_number):
    system = BASE_PROMPT.format(schema=schema) + "\n" + role_prompt(role, entity_id, student_number)
    response = await llm.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": system}, {"role": "user", "content": question}],
        temperature=0.0,
    )
    return re.sub(r"```sql|```", "", response.choices[0].message.content).strip()

# ============================== ПРОВЕРКА SQL ==============================
def validate_sql(sql: str):
    parsed = sqlparse.parse(sql)
    if not parsed:
        return False, "Не удалось распознать SQL-запрос."
    if parsed[0].get_type() != "SELECT":
        return False, "Разрешены только SELECT-запросы."
    low = sql.lower()
    for w in ["insert", "update", "delete", "drop", "alter", "truncate", "grant", "revoke"]:
        if re.search(rf"\b{w}\b", low):
            return False, f"Обнаружено запрещённое действие: {w}"
    used = set(re.findall(r"\b(?:from|join)\s+([a-z_][a-z0-9_]*)", low))
    bad = used - set(WHITELIST_TABLES)
    if bad:
        return False, "Таблицы вне whitelist: " + ", ".join(sorted(bad))
    if "limit" not in low:
        sql += " LIMIT 100"
    return True, sql

# ============================== ПРИЛОЖЕНИЕ ==============================
@asynccontextmanager
async def lifespan(app: FastAPI):
    await db_connect()
    logger.info("✅ DB pool created")
    yield
    await pool.close()

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class LoginRequest(BaseModel):
    login: str

class LoginResponse(BaseModel):
    ok: bool
    role: str | None = None
    name: str | None = None
    entity_id: int | None = None
    student_number: str | None = None
    error: str | None = None

class QueryRequest(BaseModel):
    question: str
    role: str = "applicant"
    user_name: str = ""
    entity_id: int | None = None
    student_number: str | None = None

class QueryResponse(BaseModel):
    sql: str = ""
    data: list = []
    error: str | None = None

# ----- ВХОД ПО ID (без нейросети, параметризованный запрос) -----
@app.post("/api/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    logger.info("Login attempt: %s", req.login)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT u.role, u.entity_id,
                   s.student_id_number AS student_number,
                   COALESCE(t.full_name, a.full_name) AS person_name
            FROM users u
            LEFT JOIN students s ON u.role='student' AND s.id=u.entity_id
            LEFT JOIN teachers t ON u.role='teacher' AND t.id=u.entity_id
            LEFT JOIN admins   a ON u.role='admin'   AND a.id=u.entity_id
            WHERE u.login=$1 AND u.is_active=true
            """, req.login)
    if not row:
        logger.warning("Login failed: %s", req.login)
        return LoginResponse(ok=False, error="ID не найден или пользователь неактивен.")
    logger.info("Login OK: %s -> %s", req.login, row["role"])
    return LoginResponse(ok=True, role=row["role"],
                         name=str(row["student_number"] or row["person_name"] or req.login),
                         entity_id=row["entity_id"], student_number=row["student_number"])

# ----- ВОПРОС → SQL → ОТВЕТ -----
@app.post("/api/query", response_model=QueryResponse)
async def process_query(req: QueryRequest):
    logger.info("User: %s | Role: %s | Question: %s", req.user_name or "guest", req.role, req.question)
    try:
        schema = await get_schema()
        sql = await generate_sql(req.question, schema, req.role, req.entity_id, req.student_number)
        logger.info("SQL: %s", sql)
        ok, checked = validate_sql(sql)
        if not ok:
            return QueryResponse(error=checked)
        async with pool.acquire() as conn:
            rows = await conn.fetch(checked)
        data = [dict(r) for r in rows]
        logger.info("OK, rows=%d", len(data))
        return QueryResponse(sql=checked, data=data)
    except Exception as e:
        logger.error("Error: %s", e)
        return QueryResponse(error=str(e))