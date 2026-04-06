from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta, date
import random

ROOT = os.path.dirname(os.path.abspath(__file__))
SCHEMA_PATH = os.path.join(ROOT, "schema.sql")
DATA_DIR = os.path.join(ROOT, "data")

DBS = {
    "A": os.path.join(DATA_DIR, "clinic_a.sqlite3"),
    "B": os.path.join(DATA_DIR, "clinic_b.sqlite3"),
}

STATUSES = [
    (1, "Запланирована"),
    (2, "Завершена"),
    (3, "Отменена"),
    (4, "Неявка"),
]

PAYMENT_TYPES = [
    (1, "ОМС"),
    (2, "ДМС"),
    (3, "Платно"),
    (4, "Наличный расчёт"),
    (5, "Безналичный расчёт"),
    (6, "Кредит"),
    (7, "Скидка"),
    (8, "Бесплатно"),
]

SPECIALTIES = [
    "Терапевт", "Кардиолог", "Невролог", "Хирург", "Окулист",
    "Педиатр", "Дерматолог", "Уролог", "Ортопед", "Пульмонолог",
]

# --- ФИО ПАЦИЕНТОВ (30 уникальных) ---
PATIENT_NAMES = [
    "Иван Иванов", "Алексей Смирнов", "Дмитрий Кузнецов", "Сергей Попов",
    "Андрей Васильев", "Николай Соколов", "Павел Михайлов", "Евгений Фёдоров",
    "Владимир Никитин", "Константин Орлов", "Максим Захаров", "Юрий Белов",
    "Олег Тарасов", "Роман Гусев", "Виктор Крылов", "Игорь Лебедев",
    "Артур Егоров", "Георгий Макаров", "Степан Дорофеев", "Анна Иванова",
    "Мария Смирнова", "Елена Кузнецова", "Ольга Попова", "Татьяна Морозова",
    "Наталья Волкова", "Ирина Павлова", "Дарья Романова", "Ксения Орлова",
    "Юлия Николаева", "Светлана Андреева"
]
random.shuffle(PATIENT_NAMES)

# --- ФИО ВРАЧЕЙ (30 уникальных) ---
DOCTOR_NAMES = [
    "Валерий Жуков", "Станислав Киселёв", "Григорий Исаев", "Леонид Зайцев",
    "Руслан Сафонов", "Вячеслав Корнилов", "Аркадий Фролов", "Борис Громов",
    "Анатолий Власов", "Денис Елисеев", "Пётр Анисимов", "Ярослав Терентьев",
    "Михаил Субботин", "Кирилл Афанасьев", "Тимур Абрамов", "Эдуард Кононов",
    "Людмила Сергеева", "Вера Андреева", "Инна Беляева", "Алёна Гаврилова",
    "Екатерина Ларионова", "Оксана Филиппова", "Нина Герасимова", "Лариса Демидова",
    "Полина Жданова", "Валентина Котова", "Галина Селезнёва", "Зоя Ершова",
    "Раиса Ширяева", "Любовь Капустина"
]


def load_schema() -> str:
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        return f.read()


def ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)


def random_phone() -> str:
    return "+7" + "".join(str(random.randint(0, 9)) for _ in range(10))


def make_patient(i: int):
    full_name = PATIENT_NAMES[i - 1]
    phone = random_phone()
    email = None if i % 5 == 0 else f"p{i:02d}@m.ru"
    birth = date(1980, 1, 1) + timedelta(days=i * 200)
    return (full_name, phone, email, birth.isoformat())


def make_doctor(i: int):
    full_name = DOCTOR_NAMES[i - 1]
    specialty = SPECIALTIES[(i - 1) % len(SPECIALTIES)]
    cabinet = f"{100 + i}"
    phone = random_phone()
    return (full_name, specialty, cabinet, phone)


# --- ПРИЧИНЫ ОБРАЩЕНИЯ ---
REASONS = [
    "Головная боль", "Повышенное давление", "Боль в спине", "Простудное заболевание",
    "Сильный кашель", "Боль в горле", "Высокая температура", "Аллергическая реакция",
    "Боль в животе", "Травматическое повреждение", "Профилактический осмотр", "Общая слабость",
    "Хроническая бессонница", "Частое головокружение", "Боль в суставах", "Кожная сыпь",
    "Одышка при нагрузке", "Боль в области груди", "Сильный насморк", "Проблемы с пищеварением"
]
random.shuffle(REASONS)

def make_appointment(i: int):
    base = datetime.now().replace(second=0, microsecond=0)
    visit_dt = (base + timedelta(days=i, hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    patient_id = i
    doctor_id = i
    status_id = (i % 4) + 1
    payment_type_id = (i % 8) + 1
    reason = REASONS[(i - 1) % len(REASONS)]
    duration = 10 + (i % 21)
    price = float((i * 100) % 5000)
    comment = None if i % 3 == 0 else f"Комментарий врача {i:02d}"
    return (patient_id, doctor_id, status_id, payment_type_id, visit_dt, reason, duration, price, comment)


def seed_one(db_path: str):
    if os.path.exists(db_path):
        os.remove(db_path)

    schema = load_schema()
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")

    con.executescript(schema)

    con.executemany("INSERT INTO statuses(id, name) VALUES (?, ?);", STATUSES)
    con.executemany("INSERT INTO payment_types(id, name) VALUES (?, ?);", PAYMENT_TYPES)

    patients = [make_patient(i) for i in range(1, 31)]
    doctors = [make_doctor(i) for i in range(1, 31)]

    con.executemany(
        "INSERT INTO patients(full_name, phone, email, birth_date) VALUES (?, ?, ?, ?);",
        patients
    )
    con.executemany(
        "INSERT INTO doctors(full_name, specialty, cabinet, phone) VALUES (?, ?, ?, ?);",
        doctors
    )

    appts = [make_appointment(i) for i in range(1, 31)]
    con.executemany("""
        INSERT INTO appointments(
          patient_id, doctor_id, status_id, payment_type_id,
          visit_datetime, reason, duration_minutes, price, doctor_comment
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, appts)

    con.commit()
    con.close()


def main():
    ensure_dirs()
    seed_one(DBS["A"])
    seed_one(DBS["B"])
    print("OK: created DB A and DB B")


if __name__ == "__main__":
    main()
