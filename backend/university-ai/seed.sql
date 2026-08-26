-- Факультеты
INSERT INTO faculties (name) VALUES
    ('Факультет информатики'),
    ('Математический факультет'),
    ('Экономический факультет');

-- Кафедры
INSERT INTO departments (faculty_id, name) VALUES
    (1, 'Кафедра информационных систем'),
    (1, 'Кафедра программирования'),
    (2, 'Кафедра математического анализа'),
    (3, 'Кафедра экономики');

-- Направления подготовки
INSERT INTO programs (faculty_id, name, budget_places, paid_places) VALUES
    (1, 'Информатика и вычислительная техника', 50, 30),
    (1, 'Программная инженерия', 40, 40),
    (2, 'Прикладная математика', 30, 20),
    (3, 'Экономика', 45, 60);

-- Преподаватели
INSERT INTO teachers (full_name, department_id) VALUES
    ('Петрова Анна Сергеевна', 1),
    ('Смирнов Дмитрий Владимирович', 2),
    ('Фёдоров Игорь Николаевич', 3),
    ('Никитина Елена Олеговна', 4);

-- Студенты
INSERT INTO students (student_id_number, group_name, faculty_id, enrollment_year) VALUES
    ('ST-101', 'ИУ-21', 1, 2024),
    ('ST-102', 'ИУ-21', 1, 2024),
    ('ST-103', 'ПИ-22', 1, 2023),
    ('ST-104', 'ПМ-23', 2, 2023),
    ('ST-105', 'ЭК-24', 3, 2022);

-- Дисциплины
INSERT INTO courses (name, teacher_id, semester) VALUES
    ('Базы данных', 1, 1),
    ('Математика', 2, 1),
    ('Физика', 3, 1),
    ('Программирование', 1, 2),
    ('История', 4, 2),
    ('Экономика', 4, 3);

-- Оценки Иванова (id=1): слабая математика и физика, сильное программирование
INSERT INTO grades (student_id, course_id, grade, is_passed) VALUES
    (1, 1, 5, true),
    (1, 1, 5, true),
    (1, 2, 3, true),
    (1, 2, 3, true),
    (1, 2, 4, true),
    (1, 3, 3, true),
    (1, 3, 4, true),
    (1, 4, 5, true),
    (1, 4, 5, true),
    (1, 5, 4, true);

-- Оценки остальных студентов
INSERT INTO grades (student_id, course_id, grade, is_passed) VALUES
    (2, 1, 4, true),
    (2, 2, 4, true),
    (2, 3, 3, false),
    (3, 1, 5, true),
    (3, 4, 4, true),
    (4, 2, 5, true),
    (5, 6, 4, true);

-- Абитуриенты (для вопросов про проходной балл)
INSERT INTO applicants (application_year, program_id, total_score, is_admitted) VALUES
    (2024, 1, 250, true),
    (2024, 1, 240, true),
    (2024, 1, 200, false),
    (2025, 1, 260, true),
    (2025, 2, 245, true),
    (2025, 2, 210, false),
    (2024, 3, 230, true),
    (2025, 4, 255, true);

-- Администраторы
INSERT INTO admins (full_name, position) VALUES
    ('Управление аналитики', 'Начальник отдела аналитики'),
    ('Декан информатики', 'Декан факультета информатики');