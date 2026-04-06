-- schema.sql
-- Важно: PRAGMA foreign_keys=ON включаем в коде Python на каждом соединении.

DROP TABLE IF EXISTS appointments;
DROP TABLE IF EXISTS patients;
DROP TABLE IF EXISTS doctors;
DROP TABLE IF EXISTS statuses;
DROP TABLE IF EXISTS payment_types;

CREATE TABLE patients (
  id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL
    CHECK (id BETWEEN 1 AND 3000),

  full_name TEXT NOT NULL
    CHECK (length(full_name) BETWEEN 5 AND 30),

  phone TEXT NOT NULL
    CHECK (length(phone) BETWEEN 10 AND 15),

  email TEXT NULL
    CHECK (email IS NULL OR length(email) BETWEEN 0 AND 20),

  birth_date TEXT NOT NULL
    CHECK (birth_date >= '1920-01-01')
);

CREATE TABLE doctors (
  id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL
    CHECK (id BETWEEN 1 AND 200),

  full_name TEXT NOT NULL
    CHECK (length(full_name) BETWEEN 10 AND 30),

  specialty TEXT NOT NULL
    CHECK (length(specialty) BETWEEN 5 AND 30),

  cabinet TEXT NOT NULL
    CHECK (length(cabinet) BETWEEN 1 AND 10),

  phone TEXT NOT NULL
    CHECK (length(phone) BETWEEN 10 AND 15)
);

CREATE TABLE statuses (
  id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL
    CHECK (id BETWEEN 1 AND 4),

  name TEXT NOT NULL
    CHECK (length(name) BETWEEN 6 AND 13)
);

CREATE TABLE payment_types (
  id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL
    CHECK (id BETWEEN 1 AND 8),

  name TEXT NOT NULL
    CHECK (length(name) BETWEEN 3 AND 18)
);

CREATE TABLE appointments (
  id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL
    CHECK (id BETWEEN 1 AND 10000),

  patient_id INTEGER NOT NULL
    CHECK (patient_id BETWEEN 1 AND 3000)
    REFERENCES patients(id) ON DELETE CASCADE,

  doctor_id INTEGER NOT NULL
    CHECK (doctor_id BETWEEN 1 AND 200)
    REFERENCES doctors(id) ON DELETE CASCADE,

  status_id INTEGER NOT NULL
    CHECK (status_id BETWEEN 1 AND 4)
    REFERENCES statuses(id),

  payment_type_id INTEGER NOT NULL
    CHECK (payment_type_id BETWEEN 1 AND 8)
    REFERENCES payment_types(id),

  visit_datetime TEXT NOT NULL,

  reason TEXT NOT NULL
    CHECK (length(reason) BETWEEN 5 AND 50),

  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    CHECK (created_at >= '2026-01-01 00:00:00'),

  duration_minutes INTEGER NOT NULL DEFAULT 15
    CHECK (duration_minutes BETWEEN 10 AND 30),

  price NUMERIC NOT NULL DEFAULT 0.00
    CHECK (price BETWEEN 0.00 AND 9999.99),

  doctor_comment TEXT NULL
    CHECK (doctor_comment IS NULL OR length(doctor_comment) <= 200),

  CONSTRAINT uq_doctor_slot UNIQUE (doctor_id, visit_datetime)
);

-- Индексы (не обязательны для 30 строк, но полезны под JOIN/поиск)
CREATE INDEX idx_appointments_patient ON appointments(patient_id);
CREATE INDEX idx_appointments_doctor  ON appointments(doctor_id);
CREATE INDEX idx_appointments_visit   ON appointments(visit_datetime);
CREATE INDEX idx_patients_name        ON patients(full_name);
CREATE INDEX idx_doctors_name         ON doctors(full_name);
