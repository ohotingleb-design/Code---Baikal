"""
Тесты модулей безопасности и извлечения SQL.
Запуск: pytest test_app.py -v
"""
from app import extract_sql, validate_sql, MAX_ROWS, WHITELIST


# ================= extract_sql =================

def test_extract_sql_from_tags():
    """Извлечение SQL из тегов <sql>...</sql>"""
    text = ("ОБЪЯСНЕНИЕ:\n- Таблицы: students\n"
            "<sql>\nSELECT COUNT(*) AS total FROM students\n</sql>\n"
            "ОТВЕТ: всего студентов.")
    assert extract_sql(text) == "SELECT COUNT(*) AS total FROM students"


def test_extract_sql_from_markdown():
    """Извлечение SQL из markdown блока ```sql...```"""
    text = "Вот запрос:\n```sql\nSELECT name FROM faculties\n```"
    assert extract_sql(text) == "SELECT name FROM faculties"


def test_extract_sql_markdown_inside_tags():
    """Markdown внутри тегов <sql>"""
    text = "<sql>\n```sql\nSELECT COUNT(*) FROM teachers\n```\n</sql>"
    assert extract_sql(text) == "SELECT COUNT(*) FROM teachers"


def test_extract_sql_returns_none():
    """Отсутствие SQL в тексте"""
    assert extract_sql("Привет! Я ассистент университета.") is None


def test_extract_sql_with_complex_query():
    """Сложный SQL с JOIN и подзапросами"""
    text = """
    ОБЪЯСНЕНИЕ: используем JOIN
    <sql>
    SELECT f.name, COUNT(s.id) 
    FROM faculties f 
    LEFT JOIN students s ON s.faculty_id = f.id 
    GROUP BY f.id, f.name
    </sql>
    """
    result = extract_sql(text)
    assert "SELECT" in result
    assert "FROM faculties f" in result
    assert "LEFT JOIN students s" in result


# ================= validate_sql - разрешенные запросы =================

def test_plain_select_gets_limit():
    """Простой SELECT без агрегатов получает LIMIT"""
    ok, _, sql = validate_sql("SELECT name FROM faculties")
    assert ok
    assert sql.upper().endswith(f"LIMIT {MAX_ROWS}")


def test_aggregate_without_group_has_no_limit():
    """Агрегат без GROUP BY не получает LIMIT"""
    ok, _, sql = validate_sql("SELECT COUNT(*) FROM students")
    assert ok
    assert "LIMIT" not in sql.upper()


def test_group_by_gets_limit():
    """Агрегат с GROUP BY получает LIMIT"""
    ok, _, sql = validate_sql("SELECT group_name, COUNT(*) FROM students GROUP BY group_name")
    assert ok
    assert "LIMIT" in sql.upper()


def test_with_cte_allowed():
    """CTE (WITH) разрешен"""
    q = ("WITH agg AS (SELECT faculty_id, COUNT(*) AS c "
         "FROM students GROUP BY faculty_id) "
         "SELECT f.name, agg.c FROM faculties f "
         "JOIN agg ON agg.faculty_id = f.id")
    ok, msg, _ = validate_sql(q)
    assert ok, msg


def test_multiple_joins_allowed():
    """Множественные JOIN разрешены"""
    q = ("SELECT t.full_name, d.name "
         "FROM teachers t "
         "JOIN departments d ON d.id = t.department_id "
         "JOIN faculties f ON f.id = d.faculty_id")
    ok, _, _ = validate_sql(q)
    assert ok


def test_subquery_in_where():
    """Подзапрос в WHERE разрешен"""
    q = ("SELECT name FROM faculties WHERE id IN "
         "(SELECT faculty_id FROM students)")
    ok, _, _ = validate_sql(q)
    assert ok


# ================= validate_sql - блокировки =================

def test_delete_blocked():
    """DELETE блокируется"""
    ok, _, _ = validate_sql("DELETE FROM students")
    assert not ok


def test_insert_blocked():
    """INSERT блокируется"""
    ok, _, _ = validate_sql("INSERT INTO students (id) VALUES (1)")
    assert not ok


def test_update_blocked():
    """UPDATE блокируется"""
    ok, _, _ = validate_sql("UPDATE students SET grade = 5 WHERE id = 1")
    assert not ok


def test_drop_blocked():
    """DROP блокируется"""
    ok, _, _ = validate_sql("DROP TABLE students")
    assert not ok


def test_alter_blocked():
    """ALTER блокируется"""
    ok, _, _ = validate_sql("ALTER TABLE students ADD COLUMN email TEXT")
    assert not ok


def test_truncate_blocked():
    """TRUNCATE блокируется"""
    ok, _, _ = validate_sql("TRUNCATE TABLE students")
    assert not ok


def test_create_blocked():
    """CREATE блокируется"""
    ok, _, _ = validate_sql("CREATE TABLE test (id INT)")
    assert not ok


def test_drop_and_compound_blocked():
    """Составной запрос с DROP блокируется"""
    ok, _, _ = validate_sql("SELECT 1; DROP TABLE students")
    assert not ok


def test_comments_blocked():
    """Комментарии блокируются"""
    ok, _, _ = validate_sql("SELECT name FROM faculties -- hack")
    assert not ok


def test_block_comments_blocked():
    """Блочные комментарии блокируются"""
    ok, _, _ = validate_sql("SELECT name /* hack */ FROM faculties")
    assert not ok


def test_foreign_table_blocked():
    """Таблица вне whitelist блокируется"""
    ok, msg, _ = validate_sql("SELECT * FROM secret_data")
    assert not ok
    assert "secret_data" in msg


def test_multiple_foreign_tables_blocked():
    """Несколько таблиц вне whitelist"""
    ok, msg, _ = validate_sql("SELECT * FROM users JOIN passwords ON users.id = passwords.user_id")
    assert not ok
    assert "users" in msg or "passwords" in msg


def test_sql_injection_union_blocked():
    """SQL-инъекция через UNION блокируется"""
    ok, _, _ = validate_sql("SELECT name FROM students UNION SELECT password FROM users")
    assert not ok


def test_empty_sql_blocked():
    """Пустой SQL блокируется"""
    ok, _, _ = validate_sql("")
    assert not ok


def test_none_sql_blocked():
    """None SQL блокируется"""
    ok, _, _ = validate_sql(None)
    assert not ok


# ================= validate_sql - edge cases =================

def test_case_insensitive_keywords():
    """Ключевые слова нечувствительны к регистру"""
    ok, _, _ = validate_sql("select name from faculties")
    assert ok
    
    ok, _, _ = validate_sql("DELETE FROM students")
    assert not ok


def test_whitespace_handling():
    """Обработка пробелов и переносов строк"""
    q = """
    SELECT 
        name 
    FROM 
        faculties
    """
    ok, _, sql = validate_sql(q)
    assert ok
    assert "SELECT" in sql.upper()


def test_semicolon_stripped():
    """Точка с запятой в конце удаляется"""
    ok, _, sql = validate_sql("SELECT name FROM faculties;")
    assert ok
    assert not sql.endswith(";")


def test_quoted_table_names():
    """Таблицы в кавычках распознаются"""
    ok, _, _ = validate_sql('SELECT * FROM "faculties"')
    assert ok


def test_cte_with_multiple_tables():
    """CTE с несколькими таблицами из whitelist"""
    q = ("WITH student_counts AS ("
         "  SELECT faculty_id, COUNT(*) as cnt "
         "  FROM students GROUP BY faculty_id"
         ")"
         "SELECT f.name, student_counts.cnt "
         "FROM faculties f "
         "JOIN student_counts ON student_counts.faculty_id = f.id")
    ok, msg, _ = validate_sql(q)
    assert ok, msg


def test_limit_already_present():
    """Если LIMIT уже есть, он не дублируется"""
    q = "SELECT name FROM students LIMIT 10"
    ok, _, sql = validate_sql(q)
    assert ok
    assert sql.upper().count("LIMIT") == 1


def test_complex_aggregate_expression():
    """Сложное агрегатное выражение"""
    q = "SELECT AVG(grade * 2) + 10 FROM grades"
    ok, _, sql = validate_sql(q)
    assert ok
    assert "LIMIT" not in sql.upper()


def test_nested_aggregates():
    """Вложенные агрегаты"""
    q = "SELECT COUNT(DISTINCT student_id) FROM grades"
    ok, _, sql = validate_sql(q)
    assert ok
    assert "LIMIT" not in sql.upper()


# ================= Интеграционные тесты =================

def test_all_whitelist_tables_allowed():
    """Все таблицы из whitelist разрешены"""
    for table in WHITELIST:
        ok, msg, _ = validate_sql(f"SELECT * FROM {table}")
        assert ok, f"Таблица {table} должна быть разрешена: {msg}"


def test_real_world_query_1():
    """Реальный запрос: количество студентов на факультетах"""
    q = ("SELECT f.name AS faculty, COUNT(s.id) AS student_count "
         "FROM faculties f "
         "LEFT JOIN students s ON s.faculty_id = f.id "
         "GROUP BY f.id, f.name "
         "ORDER BY student_count DESC")
    ok, _, sql = validate_sql(q)
    assert ok
    assert "LIMIT" in sql.upper()


def test_real_world_query_2():
    """Реальный запрос: динамика набора по годам"""
    q = ("SELECT application_year AS year, COUNT(*) AS applicants "
         "FROM applicants "
         "WHERE application_year >= 2020 "
         "GROUP BY application_year "
         "ORDER BY year")
    ok, _, sql = validate_sql(q)
    assert ok
    assert "LIMIT" in sql.upper()


def test_real_world_query_3():
    """Реальный запрос: средний балл по дисциплине"""
    q = ("SELECT c.name AS course, AVG(g.grade) AS avg_grade "
         "FROM courses c "
         "JOIN grades g ON g.course_id = c.id "
         "GROUP BY c.id, c.name")
    ok, _, sql = validate_sql(q)
    assert ok
    assert "LIMIT" in sql.upper()


def test_real_world_query_4():
    """Реальный запрос: простой агрегат без GROUP BY"""
    q = "SELECT COUNT(*) AS total_students FROM students"
    ok, _, sql = validate_sql(q)
    assert ok
    assert "LIMIT" not in sql.upper()


def test_real_world_query_5():
    """Реальный запрос: поиск по названию"""
    q = "SELECT name FROM faculties WHERE name ILIKE '%IT%'"
    ok, _, sql = validate_sql(q)
    assert ok
    assert "LIMIT" in sql.upper()