-- 1. ОЧИСТКА (удаляем старые таблицы, если они есть, чтобы не было ошибок)
DROP TABLE IF EXISTS grades CASCADE;
DROP TABLE IF EXISTS courses CASCADE;
DROP TABLE IF EXISTS applicants CASCADE;
DROP TABLE IF EXISTS students CASCADE;
DROP TABLE IF EXISTS staff CASCADE;
DROP TABLE IF EXISTS teachers CASCADE;
DROP TABLE IF EXISTS programs CASCADE;
DROP TABLE IF EXISTS departments CASCADE;
DROP TABLE IF EXISTS faculties CASCADE;
DROP TABLE IF EXISTS data_classification CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS admins CASCADE;

-- 2. Классификация данных и метаданные
CREATE TABLE data_classification (
    table_name VARCHAR(100),
    column_name VARCHAR(100),
    security_level VARCHAR(50),
    contains_pii BOOLEAN,
    description TEXT
);

-- 3. Справочники и структура
CREATE TABLE faculties (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    security_level VARCHAR(50) DEFAULT 'public'
);

CREATE TABLE departments (
    id SERIAL PRIMARY KEY,
    faculty_id INT REFERENCES faculties(id),
    name VARCHAR(255) NOT NULL
);

CREATE TABLE programs (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    budget_places INT,
    paid_places INT,
    security_level VARCHAR(50) DEFAULT 'public'
);

-- 4. Сотрудники (ПДн РАЗРЕШЕНЫ)
CREATE TABLE staff (
    id SERIAL PRIMARY KEY,
    full_name VARCHAR(255) NOT NULL,
    position VARCHAR(100),
    department_id INT REFERENCES departments(id),
    security_level VARCHAR(50) DEFAULT 'internal'
);

CREATE TABLE teachers (
    id SERIAL PRIMARY KEY,
    full_name VARCHAR(255) NOT NULL,
    department_id INT REFERENCES departments(id),
    security_level VARCHAR(50) DEFAULT 'internal'
);

-- 5. Студенты и Абитуриенты (ПДн ЗАПРЕЩЕНЫ, только агрегация)
CREATE TABLE students (
    id SERIAL PRIMARY KEY,
    student_id_number VARCHAR(50) UNIQUE NOT NULL,
    group_name VARCHAR(50),
    faculty_id INT REFERENCES faculties(id),
    enrollment_year INT,
    security_level VARCHAR(50) DEFAULT 'restricted'
);

CREATE TABLE applicants (
    id SERIAL PRIMARY KEY,
    application_year INT,
    program_id INT REFERENCES programs(id),
    total_score INT,
    is_admitted BOOLEAN,
    security_level VARCHAR(50) DEFAULT 'restricted'
);

-- 6. Учебный процесс
CREATE TABLE courses (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255),
    teacher_id INT REFERENCES teachers(id),
    semester VARCHAR(50)
);

CREATE TABLE grades (
    id SERIAL PRIMARY KEY,
    student_id INT REFERENCES students(id),
    course_id INT REFERENCES courses(id),
    grade INT,
    is_passed BOOLEAN
);

-- 7. Администраторы (отдельная таблица, так как не привязаны к сущностям)
CREATE TABLE admins (
    id SERIAL PRIMARY KEY,
    full_name VARCHAR(255) NOT NULL,
    position VARCHAR(100),
    security_level VARCHAR(50) DEFAULT 'confidential'
);

-- 8. Пользователи для авторизации
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    login VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    role VARCHAR(50) NOT NULL CHECK (role IN ('teacher', 'student', 'admin')),
    entity_id INT NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    security_level VARCHAR(50) DEFAULT 'confidential'
);

-- 9. Заполнение классификации
INSERT INTO data_classification (table_name, column_name, security_level, contains_pii, description) VALUES
('students', 'student_id_number', 'restricted', false, 'Идентификатор, но не ФИО'),
('teachers', 'full_name', 'internal', true, 'ФИО преподавателей разрешено'),
('staff', 'full_name', 'internal', true, 'ФИО сотрудников разрешено'),
('users', 'login', 'confidential', false, 'Логин для входа с префиксом роли'),
('users', 'password_hash', 'secret', false, 'Хеш пароля (не сам пароль)'),
('users', 'email', 'confidential', true, 'Email пользователя (ПДн)'),
('admins', 'full_name', 'confidential', true, 'ФИО администраторов');

-- 10. Заполнение тестовыми данными
INSERT INTO faculties (name) VALUES ('Факультет информационных технологий'), ('Экономический факультет');

INSERT INTO departments (faculty_id, name) VALUES 
(1, 'Кафедра баз данных'), 
(1, 'Кафедра ИИ'), 
(2, 'Кафедра макроэкономики');

INSERT INTO programs (name, budget_places, paid_places) VALUES 
('Информатика', 50, 100), 
('Экономика', 40, 80), 
('Программная инженерия', 60, 120);

INSERT INTO teachers (full_name, department_id) VALUES 
('Иванов И.И.', 1), 
('Петров П.П.', 2), 
('Сидорова А.А.', 3);

INSERT INTO students (student_id_number, group_name, faculty_id, enrollment_year) VALUES
('ST-101', 'ИТ-21-1', 1, 2021), 
('ST-102', 'ИТ-21-1', 1, 2021), 
('ST-103', 'ИТ-22-1', 1, 2022), 
('ST-104', 'ЭК-21-1', 2, 2021);

INSERT INTO applicants (application_year, program_id, total_score, is_admitted) VALUES
(2025, 1, 250, true), (2025, 1, 210, false), (2025, 2, 230, true),
(2026, 1, 260, true), (2026, 2, 240, true), (2026, 3, 220, false);

INSERT INTO courses (name, teacher_id, semester) VALUES 
('Базы данных', 1, 'Весна 2026'), 
('Машинное обучение', 2, 'Весна 2026'), 
('Макроэкономика', 3, 'Весна 2026');

INSERT INTO grades (student_id, course_id, grade, is_passed) VALUES
(1, 1, 5, true), 
(2, 1, 4, true), 
(3, 1, 2, false), 
(4, 3, 5, true);

-- 11. Администраторы
INSERT INTO admins (full_name, position) VALUES 
('Главный Админов А.А.', 'Системный администратор'),
('Безопасников Б.Б.', 'Администратор безопасности');

-- 12. Пользователи для входа (с префиксами)
INSERT INTO users (login, password_hash, role, entity_id) VALUES
-- Преподаватели: prep + ID из таблицы teachers
('prep1', '$2b$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWy', 'teacher', 1),
('prep2', '$2b$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWy', 'teacher', 2),
('prep3', '$2b$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWy', 'teacher', 3),

-- Студенты: stud + student_id_number из таблицы students
('studST-101', '$2b$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWy', 'student', 1),
('studST-102', '$2b$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWy', 'student', 2),
('studST-103', '$2b$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWy', 'student', 3),
('studST-104', '$2b$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWy', 'student', 4),

-- Администраторы: admin + ID из таблицы admins
('admin1', '$2b$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWy', 'admin', 1),
('admin2', '$2b$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWy', 'admin', 2);