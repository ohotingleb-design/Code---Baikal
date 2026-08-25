"""Тесты модулей безопасности и извлечения SQL.
Запуск: pytest test_app.py -v
"""
from app import extract_sql, validate_sql, MAX_ROWS


# ================= extract_sql =================

def test_extract_sql_from_tags():
    text = ("ОБЪЯСНЕНИЕ:\n- Таблицы: students\n"
            "<sql>\nSELECT COUNT(*) AS total FROM students\n</sql>\n"
            "ОТВЕТ: всего студентов.")
    assert extract_sql(text) == "SELECT COUNT(*) AS total FROM students"


def test_extract_sql_from_markdown():
    text = "Вот запрос:\n```sql\nSELECT name FROM faculties\n```"
    assert extract_sql(text) == "SELECT name FROM faculties"


def test_extract_sql_markdown_inside_tags():
    text = "<sql>\n```sql\nSELECT COUNT(*) FROM teachers\n```\n</sql>"
    assert extract_sql(text) == "SELECT COUNT(*) FROM teachers"


def test_extract_sql_returns_none():
    assert extract_sql("Привет! Я ассистент университета.") is None


# ================= validate_sql =================

def test_plain_select_gets_limit():
    ok, _, sql = validate_sql("SELECT name FROM faculties")
    assert ok
    assert sql.upper().endswith(f"LIMIT {MAX_ROWS}")


def test_aggregate_without_group_has_no_limit():
    ok, _, sql = validate_sql("SELECT COUNT(*) FROM students")
    assert ok
    assert "LIMIT" not in sql.upper()


def test_group_by_gets_limit():
    ok, _, sql = validate_sql("SELECT group_name, COUNT(*) FROM students GROUP BY group_name")
    assert ok
    assert "LIMIT" in sql.upper()


def test_delete_blocked():
    ok, _, _ = validate_sql("DELETE FROM students")
    assert not ok


def test_insert_blocked():
    ok, _, _ = validate_sql("INSERT INTO students (id) VALUES (1)")
    assert not ok


def test_drop_and_compound_blocked():
    ok, _, _ = validate_sql("SELECT 1; DROP TABLE students")
    assert not ok


def test_comments_blocked():
    ok, _, _ = validate_sql("SELECT name FROM faculties -- hack")
    assert not ok


def test_foreign_table_blocked():
    ok, msg, _ = validate_sql("SELECT * FROM secret_data")
    assert not ok
    assert "secret_data" in msg


def test_with_cte_allowed():
    q = ("WITH agg AS (SELECT faculty_id, COUNT(*) AS c "
         "FROM students GROUP BY faculty_id) "
         "SELECT f.name, agg.c FROM faculties f "
         "JOIN agg ON agg.faculty_id = f.id")
    ok, msg, _ = validate_sql(q)
    assert ok, msg