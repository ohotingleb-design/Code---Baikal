-- ================= 1. ОЧИСТКА =================
DROP TABLE IF EXISTS grades CASCADE;
DROP TABLE IF EXISTS courses CASCADE;
DROP TABLE IF EXISTS applicants CASCADE;
DROP TABLE IF EXISTS students CASCADE;
DROP TABLE IF EXISTS teachers CASCADE;
DROP TABLE IF EXISTS programs CASCADE;
DROP TABLE IF EXISTS departments CASCADE;
DROP TABLE IF EXISTS faculties CASCADE;
DROP TABLE IF EXISTS data_classification CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS admins CASCADE;

-- ================= 2. ТАБЛИЦЫ =================
CREATE TABLE data_classification (
    table_name VARCHAR(100), column_name VARCHAR(100),
    security_level VARCHAR(50), contains_pii BOOLEAN, description TEXT);

CREATE TABLE faculties (
    id SERIAL PRIMARY KEY, name VARCHAR(255) NOT NULL,
    security_level VARCHAR(50) DEFAULT 'public');

CREATE TABLE departments (
    id SERIAL PRIMARY KEY, faculty_id INT REFERENCES faculties(id),
    name VARCHAR(255) NOT NULL);

CREATE TABLE programs (
    id SERIAL PRIMARY KEY, faculty_id INT REFERENCES faculties(id),
    name VARCHAR(255) NOT NULL, budget_places INT, paid_places INT,
    security_level VARCHAR(50) DEFAULT 'public');

CREATE TABLE teachers (
    id SERIAL PRIMARY KEY, full_name VARCHAR(255) NOT NULL,
    department_id INT REFERENCES departments(id),
    security_level VARCHAR(50) DEFAULT 'internal');

CREATE TABLE students (
    id SERIAL PRIMARY KEY, student_id_number VARCHAR(50) UNIQUE NOT NULL,
    group_name VARCHAR(50), faculty_id INT REFERENCES faculties(id),
    enrollment_year INT, security_level VARCHAR(50) DEFAULT 'restricted');

CREATE TABLE applicants (
    id SERIAL PRIMARY KEY, application_year INT,
    program_id INT REFERENCES programs(id), total_score INT,
    is_admitted BOOLEAN, security_level VARCHAR(50) DEFAULT 'restricted');

CREATE TABLE courses (
    id SERIAL PRIMARY KEY, name VARCHAR(255),
    teacher_id INT REFERENCES teachers(id), semester VARCHAR(50));

CREATE TABLE grades (
    id SERIAL PRIMARY KEY, student_id INT REFERENCES students(id),
    course_id INT REFERENCES courses(id),
    grade INT CHECK (grade BETWEEN 2 AND 5), is_passed BOOLEAN);

CREATE TABLE admins (
    id SERIAL PRIMARY KEY, full_name VARCHAR(255) NOT NULL,
    position VARCHAR(100), security_level VARCHAR(50) DEFAULT 'confidential');

CREATE TABLE users (
    id SERIAL PRIMARY KEY, login VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL, email VARCHAR(255),
    role VARCHAR(50) NOT NULL CHECK (role IN ('teacher','student','admin')),
    entity_id INT NOT NULL, is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    security_level VARCHAR(50) DEFAULT 'confidential');

-- ================= 3. СПРАВОЧНИКИ =================
INSERT INTO faculties (name) VALUES
('Факультет информационных технологий (ИТ)'), ('Экономический факультет'),
('Факультет математики и естественных наук'), ('Юридический факультет'),
('Факультет филологии и межкультурной коммуникации'), ('Инженерный факультет');

INSERT INTO departments (faculty_id, name) VALUES
(1,'Кафедра баз данных и информационных систем'), (1,'Кафедра ИИ и анализа данных'), (1,'Кафедра программной инженерии'),
(2,'Кафедра макроэкономики'), (2,'Кафедра финансов и кредита'), (2,'Кафедра менеджмента и маркетинга'),
(3,'Кафедра прикладной математики'), (3,'Кафедра физики и технологий'), (3,'Кафедра химии и экологии'),
(4,'Кафедра теории и истории права'), (4,'Кафедра гражданского права'), (4,'Кафедра уголовного права'),
(5,'Кафедра русского языка'), (5,'Кафедра иностранных языков'), (5,'Кафедра литературы и журналистики'),
(6,'Кафедра механики и машиностроения'), (6,'Кафедра электротехники'), (6,'Кафедра строительства и архитектуры');

INSERT INTO programs (faculty_id, name, budget_places, paid_places) VALUES
(1,'Информатика',50,100), (1,'Программная инженерия',60,120), (1,'Прикладной анализ данных',40,80),
(2,'Экономика',40,80), (2,'Менеджмент',30,90), (2,'Финансы и кредит',35,70),
(3,'Прикладная математика',45,60), (3,'Физика и технологии',30,40),
(4,'Юриспруденция',40,120), (4,'Правоохранительная деятельность',25,50),
(5,'Филология',25,30), (5,'Журналистика',20,60),
(6,'Машиностроение',55,45), (6,'Строительство',45,55);

-- ================= 4. ПРЕПОДАВАТЕЛИ (60) =================
INSERT INTO teachers (full_name, department_id)
SELECT
  (ARRAY['Иванов','Петров','Сидоров','Кузнецов','Смирнов','Попов','Соколов','Лебедев','Козлов','Новиков','Морозов','Волков','Павлов','Семёнов','Голубев','Виноградов','Богданов','Воробьёв','Фёдоров','Михайлов'])[(floor(random()*20))::int + 1]
  || ' ' || (ARRAY['А','Б','В','Г','Д','Е','И','К','Л','М','Н','О','П','Р','С'])[(floor(random()*15))::int + 1] || '. '
  || (ARRAY['А','Б','В','Г','Д','Е','И','К','Л','М','Н','О','П','Р','С'])[(floor(random()*15))::int + 1] || '.',
  ((g - 1) % 18) + 1
FROM generate_series(1,60) g;

-- ================= 5. АДМИНИСТРАТОРЫ (5) =================
INSERT INTO admins (full_name, position)
SELECT
  (ARRAY['Админов','Безопасников','Системов','Сетевиков','Хранов'])[g] || ' '
  || (ARRAY['А','Б','В','Г','Д'])[g] || '. ' || (ARRAY['А','Б','В','Г','Д'])[(g % 5) + 1] || '.',
  (ARRAY['Системный администратор','Администратор безопасности','Администратор БД','Администратор приложений','Администратор инфраструктуры'])[g]
FROM generate_series(1,5) g;

-- ================= 6. СТУДЕНТЫ (5000, БЕЗ ФИО — политика ПДн) =================
INSERT INTO students (student_id_number, group_name, faculty_id, enrollment_year)
SELECT
  'ST-' || lpad(g::text, 5, '0'),
  (ARRAY['ИТ','ЭК','МН','ЮР','ФЛ','ИН'])[fac] || '-' || (yr - 2000) || '-' || grp,
  fac, yr
FROM (
  SELECT g, (floor(random()*6))::int + 1 AS fac,
         2021 + (floor(random()*5))::int AS yr,
         (floor(random()*3))::int + 1 AS grp
  FROM generate_series(1,5000) g
) t;

-- ================= 7. АБИТУРИЕНТЫ (30 000 заявлений) =================
INSERT INTO applicants (application_year, program_id, total_score, is_admitted)
SELECT yr, prog, score, score >= cutoff
FROM (
  SELECT 2022 + (floor(random()*5))::int AS yr,
         (floor(random()*14))::int + 1 AS prog,
         140 + (floor(random()*161))::int AS score,
         200 + (floor(random()*60))::int AS cutoff
  FROM generate_series(1,30000)
) t;

-- ================= 8. ДИСЦИПЛИНЫ (~144) =================
INSERT INTO courses (name, teacher_id, semester)
SELECT
  (ARRAY['Базы данных','Машинное обучение','Математический анализ','Линейная алгебра','Экономика','Менеджмент','Правоведение','Философия','История','Иностранный язык','Физика','Химия','Программирование','Веб-разработка','Статистика','Бухгалтерский учёт','Финансы','Маркетинг','Криминалистика','Журналистика','Редактирование','Черчение','Механика','Электротехника','Сопротивление материалов','Дискретная математика','Операционные системы','Компьютерные сети','Психология','Социология'])[(floor(random()*30))::int + 1],
  (SELECT t.id FROM teachers t WHERE t.department_id = d ORDER BY random() LIMIT 1),
  (ARRAY['Осень 2025','Весна 2026','Осень 2026'])[(floor(random()*3))::int + 1]
FROM generate_series(1,18) d, generate_series(1,8) n;

-- ================= 9. ОЦЕНКИ (~50 000) =================
INSERT INTO grades (student_id, course_id, grade, is_passed)
SELECT id, course_id, gr, gr >= 3
FROM (
  SELECT s.id, c.course_id, 2 + (floor(random()*4))::int AS gr
  FROM students s
  CROSS JOIN LATERAL (
    SELECT co.id AS course_id
    FROM courses co JOIN teachers t ON t.id = co.teacher_id
    WHERE t.department_id IN (SELECT id FROM departments WHERE faculty_id = s.faculty_id)
    ORDER BY random() LIMIT 10
  ) c
) x;

-- ================= 10. ИНДЕКСЫ =================
CREATE INDEX idx_students_faculty ON students(faculty_id);
CREATE INDEX idx_students_year ON students(enrollment_year);
CREATE INDEX idx_grades_student ON grades(student_id);
CREATE INDEX idx_grades_course ON grades(course_id);
CREATE INDEX idx_applicants_prog_year ON applicants(program_id, application_year);
CREATE INDEX idx_courses_teacher ON courses(teacher_id);
CREATE INDEX idx_departments_faculty ON departments(faculty_id);
CREATE INDEX idx_teachers_dept ON teachers(department_id);

-- ================= 11. ПОЛЬЗОВАТЕЛИ =================
INSERT INTO users (login, password_hash, role, entity_id)
SELECT 'stud' || student_id_number, '$2b$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWy', 'student', id FROM students;
INSERT INTO users (login, password_hash, role, entity_id)
SELECT 'prep' || id, '$2b$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWy', 'teacher', id FROM teachers;
INSERT INTO users (login, password_hash, role, entity_id)
SELECT 'admin' || id, '$2b$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWy', 'admin', id FROM admins;

-- ================= 12. КЛАССИФИКАЦИЯ ПДн =================
INSERT INTO data_classification (table_name, column_name, security_level, contains_pii, description) VALUES
('students', 'student_id_number', 'restricted', false, 'Идентификатор, но не ФИО'),
('teachers', 'full_name', 'internal', true, 'ФИО преподавателей разрешено'),
('users', 'login', 'confidential', false, 'Логин для входа'),
('users', 'password_hash', 'secret', false, 'Хеш пароля (не сам пароль)'),
('users', 'email', 'confidential', true, 'Email пользователя (ПДн)'),
('admins', 'full_name', 'confidential', true, 'ФИО администраторов');

-- ================= 13. ПРАВА =================
GRANT USAGE ON SCHEMA public TO db11_user;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO db11_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO db11_user;

ANALYZE;