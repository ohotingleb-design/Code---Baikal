"""
Одноразовая миграция паролей из открытого вида в bcrypt-хеши.
Запуск: python migrate_passwords.py
"""
import psycopg
from psycopg.rows import dict_row
import bcrypt
from dotenv import load_dotenv
import os

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "university_db")
DB_USER = os.getenv("DB_USER", "db11_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "12345")

conn = psycopg.connect(
    host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
    user=DB_USER, password=DB_PASSWORD, row_factory=dict_row
)
cur = conn.cursor()

# 1. Проверяем длину поля password — должно быть минимум 60 символов
cur.execute("""
    SELECT character_maximum_length
    FROM information_schema.columns
    WHERE table_name = 'users' AND column_name = 'password'
""")
row = cur.fetchone()
max_len = row['character_maximum_length'] if row else None
print(f"Текущая длина поля password: {max_len}")

if max_len is not None and max_len < 60:
    print("⚠️  Поле слишком короткое для хеша. Увеличиваю до 255...")
    cur.execute("ALTER TABLE users ALTER COLUMN password TYPE VARCHAR(255)")
    conn.commit()
    print("✅ Поле расширено до 255 символов")

# 2. Достаём всех пользователей, у которых пароль ещё НЕ хеш
# Хеш всегда начинается с $2b$ или $2a$
cur.execute("""
    SELECT login, password
    FROM users
    WHERE password NOT LIKE '$2b$%' AND password NOT LIKE '$2a$%'
""")
users = cur.fetchall()
print(f"Найдено пользователей с открытыми паролями: {len(users)}")

# 3. Хешируем каждый пароль
for u in users:
    plain = u['password'].encode('utf-8')
    hashed = bcrypt.hashpw(plain, bcrypt.gensalt(rounds=12)).decode('utf-8')
    cur.execute(
        "UPDATE users SET password = %s WHERE login = %s",
        (hashed, u['login'])
    )
    print(f"  ✅ {u['login']}: пароль захеширован")

conn.commit()
conn.close()
print(f"🎉 Готово! Мигрировано пользователей: {len(users)}")