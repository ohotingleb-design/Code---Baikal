"""
Создание нового пользователя с хешированным паролем.
Запуск: python create_user.py <login> <password> <role> <full_name>
"""
import sys
import psycopg
import bcrypt
from dotenv import load_dotenv
import os

load_dotenv()

if len(sys.argv) < 5:
    print("Использование: python create_user.py <login> <password> <role> <full_name>")
    sys.exit(1)

login, password, role, full_name = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]

hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=12)).decode('utf-8')

conn = psycopg.connect(
    host=os.getenv("DB_HOST", "127.0.0.1"),
    port=int(os.getenv("DB_PORT", "5432")),
    dbname=os.getenv("DB_NAME", "university_db"),
    user=os.getenv("DB_USER", "db11_user"),
    password=os.getenv("DB_PASSWORD", "12345")
)
cur = conn.cursor()

try:
    cur.execute("""
        INSERT INTO users (login, password, role, full_name)
        VALUES (%s, %s, %s, %s)
    """, (login, hashed, role, full_name))
    conn.commit()
    print(f"✅ Пользователь '{login}' создан (пароль захеширован)")
except psycopg.errors.UniqueViolation:
    print(f"❌ Пользователь '{login}' уже существует")
finally:
    conn.close()