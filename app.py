# app.py
from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Tuple
## import pyodbc

print("pyodbc подключен")

from flask import (
    Flask, g, render_template, request, redirect, url_for,
    session, flash, jsonify
)

APP_ROOT = os.path.dirname(os.path.abspath(__file__))

DB_MAP = {
    "A": os.path.join(APP_ROOT, "data", "clinic_a.sqlite3"),
    "B": os.path.join(APP_ROOT, "data", "clinic_b.sqlite3"),
}

ALLOWED_ADMIN_TABLES = {
    "patients", "doctors", "appointments", "statuses", "payment_types"
}

def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")

    @app.context_processor
    def inject_globals():
        return {
            "active_db_key": session.get("db_key", "A"),
            "today": date.today().isoformat(),
            # datetime-local требует формат YYYY-MM-DDTHH:MM
            "now_local_dt": datetime.now().strftime("%Y-%m-%dT%H:%M"),
            "min_visit_dt": (datetime.now().replace(second=0, microsecond=0)
                             .replace(year=datetime.now().year - 5)).strftime("%Y-%m-%dT%H:%M"),
            "max_visit_dt": (datetime.now().replace(second=0, microsecond=0)
                             .replace(year=datetime.now().year + 1)).strftime("%Y-%m-%dT%H:%M"),
        }

    def get_active_db_path() -> str:
        db_key = session.get("db_key", "A")
        return DB_MAP.get(db_key, DB_MAP["A"])

    def get_db() -> sqlite3.Connection:
        # Соединение на запрос + кэш в g (1 request = 1 connection)
        if "db" not in g:
            db_path = get_active_db_path()
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            # FK ВКЛЮЧАТЬ НА КАЖДОМ СОЕДИНЕНИИ
            conn.execute("PRAGMA foreign_keys = ON;")
            g.db = conn
        return g.db

    @app.teardown_appcontext
    def close_db(exception: Optional[BaseException]) -> None:
        db = g.pop("db", None)
        if db is not None:
            db.close()

    def query_all(sql: str, params: Tuple[Any, ...] = ()) -> List[sqlite3.Row]:
        cur = get_db().execute(sql, params)
        rows = cur.fetchall()
        cur.close()
        return rows

    def execute(sql: str, params: Tuple[Any, ...] = ()) -> int:
        db = get_db()
        cur = db.execute(sql, params)
        db.commit()
        last_id = cur.lastrowid
        cur.close()
        return last_id

    def dt_local_to_sqlite(dt_local: str) -> str:
        """
        HTML datetime-local обычно 'YYYY-MM-DDTHH:MM'.
        В БД храним 'YYYY-MM-DD HH:MM:SS' (ISO-подобный формат).
        """
        if not dt_local:
            return ""
        if "T" in dt_local:
            dt_local = dt_local.replace("T", " ")
        # дополним секунды, чтобы сравнения BETWEEN были стабильнее
        if len(dt_local) == 16:  # YYYY-MM-DD HH:MM
            dt_local += ":00"
        return dt_local

    @app.get("/switch-db/<db_key>")
    def switch_db(db_key: str):
        if db_key not in DB_MAP:
            flash("Неизвестный ключ БД.", "danger")
            return redirect(url_for("index"))
        session["db_key"] = db_key
        next_url = request.args.get("next") or url_for("index")
        flash(f"Активная база переключена на {db_key}.", "info")
        return redirect(next_url)

    # ---------- Главная ----------
    @app.get("/")
    def index():
        patients = query_all("SELECT id, full_name FROM patients ORDER BY full_name;")
        doctors = query_all("SELECT id, full_name, specialty FROM doctors ORDER BY full_name;")
        statuses = query_all("SELECT id, name FROM statuses ORDER BY id;")
        payment_types = query_all("SELECT id, name FROM payment_types ORDER BY id;")

        appointments = query_all("""
            SELECT
              a.id,
              a.visit_datetime,
              a.reason,
              a.duration_minutes,
              a.price,
              p.full_name AS patient_name,
              d.full_name AS doctor_name,
              s.name AS status_name,
              pt.name AS payment_type_name
            FROM appointments a
            JOIN patients p ON p.id = a.patient_id
            JOIN doctors d ON d.id = a.doctor_id
            JOIN statuses s ON s.id = a.status_id
            JOIN payment_types pt ON pt.id = a.payment_type_id
            ORDER BY a.visit_datetime DESC
            LIMIT 200;
        """)

        return render_template(
            "index.html",
            patients=patients,
            doctors=doctors,
            statuses=statuses,
            payment_types=payment_types,
            appointments=appointments,
        )

    @app.post("/appointments/create")
    def create_appointment():
        try:
            patient_id = int(request.form["patient_id"])
            doctor_id = int(request.form["doctor_id"])
            status_id = int(request.form["status_id"])
            payment_type_id = int(request.form["payment_type_id"])
            visit_dt = dt_local_to_sqlite(request.form["visit_datetime"])
            reason = request.form["reason"].strip()
            duration = int(request.form.get("duration_minutes") or 15)
            price = float(request.form.get("price") or 0.0)
            doctor_comment = request.form.get("doctor_comment")
            doctor_comment = doctor_comment.strip() if doctor_comment else None

            execute("""
                INSERT INTO appointments(
                    patient_id, doctor_id, status_id, payment_type_id,
                    visit_datetime, reason, duration_minutes, price, doctor_comment
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (patient_id, doctor_id, status_id, payment_type_id,
                  visit_dt, reason, duration, price, doctor_comment))

            flash("Запись успешно создана.", "success")
        except (ValueError, KeyError):
            flash("Некорректные данные формы. Проверьте поля.", "danger")
        except sqlite3.IntegrityError as e:
            # FK/UNIQUE/CHECK
            flash(f"Ошибка БД: {e}", "danger")
        return redirect(url_for("index"))

    # ---------- API для модалок ----------
    @app.post("/api/patients/create")
    def api_create_patient():
        try:
            full_name = request.form["full_name"].strip()
            phone = request.form["phone"].strip()
            email = request.form.get("email")
            email = email.strip() if email else None
            birth_date = request.form["birth_date"].strip()

            new_id = execute("""
                INSERT INTO patients(full_name, phone, email, birth_date)
                VALUES (?, ?, ?, ?);
            """, (full_name, phone, email, birth_date))

            row = query_all("SELECT id, full_name FROM patients WHERE id=?;", (new_id,))[0]
            return jsonify({"ok": True, "id": row["id"], "label": row["full_name"]})
        except (KeyError, ValueError):
            return jsonify({"ok": False, "error": "Некорректные данные."}), 400
        except sqlite3.IntegrityError as e:
            return jsonify({"ok": False, "error": str(e)}), 400

    @app.post("/api/doctors/create")
    def api_create_doctor():
        try:
            full_name = request.form["full_name"].strip()
            specialty = request.form["specialty"].strip()
            cabinet = request.form["cabinet"].strip()
            phone = request.form["phone"].strip()

            new_id = execute("""
                INSERT INTO doctors(full_name, specialty, cabinet, phone)
                VALUES (?, ?, ?, ?);
            """, (full_name, specialty, cabinet, phone))

            row = query_all("SELECT id, full_name FROM doctors WHERE id=?;", (new_id,))[0]
            return jsonify({"ok": True, "id": row["id"], "label": row["full_name"]})
        except (KeyError, ValueError):
            return jsonify({"ok": False, "error": "Некорректные данные."}), 400
        except sqlite3.IntegrityError as e:
            return jsonify({"ok": False, "error": str(e)}), 400

    # ---------- Поиск ----------
    @app.get("/search")
    def search():
        mode = request.args.get("mode", "one")

        results: List[sqlite3.Row] = []
        meta: Dict[str, Any] = {"mode": mode}

        # справочники для форм
        statuses = query_all("SELECT id, name FROM statuses ORDER BY id;")
        payment_types = query_all("SELECT id, name FROM payment_types ORDER BY id;")
        patients = query_all("SELECT id, full_name FROM patients ORDER BY full_name;")
        doctors = query_all("SELECT id, full_name FROM doctors ORDER BY full_name;")
        specialties = query_all("SELECT DISTINCT specialty FROM doctors ORDER BY specialty;")
        cabinets = query_all("SELECT DISTINCT cabinet FROM doctors ORDER BY cabinet;")

        if mode == "one":
            entity = request.args.get("entity", "patients")
            meta["entity"] = entity

            if entity == "patients":
                full_name_prefix = (request.args.get("full_name_prefix") or "").strip()
                phone_contains = (request.args.get("phone_contains") or "").strip()
                bd_from = (request.args.get("birth_date_from") or "").strip()
                bd_to = (request.args.get("birth_date_to") or "").strip()

                where = []
                params: List[Any] = []

                if full_name_prefix:
                    where.append("full_name LIKE ?")
                    params.append(full_name_prefix + "%")
                if phone_contains:
                    where.append("phone LIKE ?")
                    params.append("%" + phone_contains + "%")
                if bd_from and bd_to:
                    where.append("birth_date BETWEEN ? AND ?")
                    params.extend([bd_from, bd_to])
                elif bd_from:
                    where.append("birth_date >= ?")
                    params.append(bd_from)
                elif bd_to:
                    where.append("birth_date <= ?")
                    params.append(bd_to)

                sql = "SELECT id, full_name, phone, email, birth_date FROM patients"
                if where:
                    sql += " WHERE " + " AND ".join(where)
                sql += " ORDER BY full_name LIMIT 200;"

                results = query_all(sql, tuple(params))

            elif entity == "doctors":
                full_name_prefix = (request.args.get("full_name_prefix") or "").strip()
                specialty = (request.args.get("specialty") or "").strip()
                cabinet = (request.args.get("cabinet") or "").strip()

                where = []
                params: List[Any] = []

                if full_name_prefix:
                    where.append("full_name LIKE ?")
                    params.append(full_name_prefix + "%")
                if specialty:
                    where.append("specialty = ?")
                    params.append(specialty)
                if cabinet:
                    where.append("cabinet = ?")
                    params.append(cabinet)

                sql = "SELECT id, full_name, specialty, cabinet, phone FROM doctors"
                if where:
                    sql += " WHERE " + " AND ".join(where)
                sql += " ORDER BY full_name LIMIT 200;"

                results = query_all(sql, tuple(params))

            elif entity == "appointments":
                status_id = (request.args.get("status_id") or "").strip()
                payment_type_id = (request.args.get("payment_type_id") or "").strip()
                dt_from = (request.args.get("visit_from") or "").strip()
                dt_to = (request.args.get("visit_to") or "").strip()

                where = []
                params: List[Any] = []

                if status_id:
                    where.append("a.status_id = ?")
                    params.append(int(status_id))
                if payment_type_id:
                    where.append("a.payment_type_id = ?")
                    params.append(int(payment_type_id))
                if dt_from and dt_to:
                    where.append("a.visit_datetime BETWEEN ? AND ?")
                    params.append(dt_local_to_sqlite(dt_from))
                    params.append(dt_local_to_sqlite(dt_to))
                sql = """
                    SELECT
                    a.id,
                    a.visit_datetime,
                    a.reason,
                    a.duration_minutes,
                    a.price,
                    a.doctor_comment,
                    p.full_name AS patient_name,
                    d.full_name AS doctor_name,
                    s.name AS status_name,
                    pt.name AS payment_type_name
                    FROM appointments a
                    JOIN patients p ON p.id = a.patient_id
                    JOIN doctors d ON d.id = a.doctor_id
                    JOIN statuses s ON s.id = a.status_id
                    JOIN payment_types pt ON pt.id = a.payment_type_id
                """
                if where:
                    sql += " WHERE " + " AND ".join(where)
                sql += " ORDER BY a.visit_datetime DESC LIMIT 200;"

                results = query_all(sql, tuple(params))

        elif mode == "two":
            # SELECT p.full_name, a.visit_datetime ... JOIN ...
            patient_id = (request.args.get("patient_id") or "").strip()
            visit_dt = (request.args.get("visit_datetime") or "").strip()
            meta["patient_id"] = patient_id
            meta["visit_datetime"] = visit_dt

            if patient_id:
                sql = """
                    SELECT
                      p.full_name AS patient_name,
                      a.visit_datetime,
                      d.full_name AS doctor_name,
                      a.reason
                    FROM appointments a
                    JOIN patients p ON p.id = a.patient_id
                    JOIN doctors d ON d.id = a.doctor_id
                    WHERE a.patient_id = ?
                """
                params: List[Any] = [int(patient_id)]
                if visit_dt:
                    sql += " AND a.visit_datetime = ?"
                    params.append(dt_local_to_sqlite(visit_dt))
                sql += " ORDER BY a.visit_datetime DESC LIMIT 200;"
                results = query_all(sql, tuple(params))

        elif mode == "agg":
            # SELECT doctor_id, COUNT(id) ... GROUP BY ...
            results = query_all("""
                SELECT
                  d.full_name AS doctor_name,
                  d.specialty,
                  COUNT(a.id) AS appointments_count
                FROM doctors d
                LEFT JOIN appointments a ON a.doctor_id = d.id
                GROUP BY d.id
                ORDER BY appointments_count DESC, d.full_name ASC;
            """)
        if results is not None:
            results = [dict(row) for row in results]

        return render_template(
            "search.html",
            mode=mode,
            meta=meta,
            results=results,
            statuses=statuses,
            payment_types=payment_types,
            patients=patients,
            doctors=doctors,
            specialties=specialties,
            cabinets=cabinets,
        )

    @app.get("/api/options/visits-by-patient")
    def api_visits_by_patient():
        patient_id = request.args.get("patient_id", "").strip()
        if not patient_id:
            return jsonify({"ok": True, "items": []})
        try:
            rows = query_all("""
                SELECT visit_datetime
                FROM appointments
                WHERE patient_id = ?
                ORDER BY visit_datetime DESC;
            """, (int(patient_id),))
            items = [{"value": r["visit_datetime"], "label": r["visit_datetime"]} for r in rows]
            return jsonify({"ok": True, "items": items})
        except ValueError:
            return jsonify({"ok": False, "error": "bad patient_id"}), 400

    # ---------- Администрирование ----------
    @app.get("/admin")
    def admin():
        table = request.args.get("table", "patients")
        if table not in ALLOWED_ADMIN_TABLES:
            table = "patients"

        rows = query_all(f"SELECT * FROM {table} LIMIT 200;")

        # Для appointments нужны справочники
        patients = query_all("SELECT id, full_name FROM patients ORDER BY full_name;")
        doctors = query_all("SELECT id, full_name FROM doctors ORDER BY full_name;")
        statuses = query_all("SELECT id, name FROM statuses ORDER BY id;")
        payment_types = query_all("SELECT id, name FROM payment_types ORDER BY id;")

        return render_template(
            "admin.html",
            table=table,
            rows=rows,
            patients=patients,
            doctors=doctors,
            statuses=statuses,
            payment_types=payment_types,
        )

    @app.post("/admin/<table>/create")
    def admin_create(table: str):
        if table not in ALLOWED_ADMIN_TABLES:
            flash("Недопустимая таблица.", "danger")
            return redirect(url_for("admin"))

        try:
            if table == "patients":
                execute("""
                    INSERT INTO patients(full_name, phone, email, birth_date)
                    VALUES (?, ?, ?, ?);
                """, (
                    request.form["full_name"].strip(),
                    request.form["phone"].strip(),
                    (request.form.get("email") or "").strip() or None,
                    request.form["birth_date"].strip(),
                ))
                flash("Пациент добавлен.", "success")

            elif table == "doctors":
                execute("""
                    INSERT INTO doctors(full_name, specialty, cabinet, phone)
                    VALUES (?, ?, ?, ?);
                """, (
                    request.form["full_name"].strip(),
                    request.form["specialty"].strip(),
                    request.form["cabinet"].strip(),
                    request.form["phone"].strip(),
                ))
                flash("Врач добавлен.", "success")

            elif table == "appointments":
                execute("""
                    INSERT INTO appointments(
                      patient_id, doctor_id, status_id, payment_type_id,
                      visit_datetime, reason, duration_minutes, price, doctor_comment
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    int(request.form["patient_id"]),
                    int(request.form["doctor_id"]),
                    int(request.form["status_id"]),
                    int(request.form["payment_type_id"]),
                    dt_local_to_sqlite(request.form["visit_datetime"]),
                    request.form["reason"].strip(),
                    int(request.form.get("duration_minutes") or 15),
                    float(request.form.get("price") or 0),
                    (request.form.get("doctor_comment") or "").strip() or None,
                ))
                flash("Запись добавлена.", "success")

            elif table == "statuses":
                execute("INSERT INTO statuses(name) VALUES (?);", (request.form["name"].strip(),))
                flash("Статус добавлен.", "success")

            elif table == "payment_types":
                execute("INSERT INTO payment_types(name) VALUES (?);", (request.form["name"].strip(),))
                flash("Тип оплаты добавлен.", "success")

        except sqlite3.IntegrityError as e:
            flash(f"Ошибка ограничения: {e}", "danger")
        except (ValueError, KeyError):
            flash("Некорректные данные формы.", "danger")

        return redirect(url_for("admin", table=table))

    @app.post("/admin/<table>/delete/<int:id>")
    def admin_delete(table: str, id: int):
        if table not in ALLOWED_ADMIN_TABLES:
            flash("Недопустимая таблица.", "danger")
            return redirect(url_for("admin"))
        
        if table in ("statuses", "payment_types"):
            flash("Эти записи нельзя удалять", "danger")
            return redirect(url_for("admin", table=table))

        try:
            execute(f"DELETE FROM {table} WHERE id = ?", (id,))
            flash("Строка удалена.", "success")
        except sqlite3.IntegrityError as e:
            flash(f"Ошибка БД: {e}", "danger")

        return redirect(url_for("admin", table=table))

    return app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
