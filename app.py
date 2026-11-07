
from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
import os
import re
from pathlib import Path
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "temporary-development-key")

DB_PATH = Path(__file__).with_name("college.db")

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                roll_no TEXT NOT NULL UNIQUE,
                course TEXT NOT NULL,
                semester TEXT NOT NULL,
                email TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS notices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                details TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        count = conn.execute(
            "SELECT COUNT(*) FROM notices"
        ).fetchone()[0]

        if count == 0:
            conn.executemany(
                "INSERT INTO notices (title, details) VALUES (?, ?)",
                [
                    ("Welcome to College Portal",
                     "Welcome to our college website."),
                    ("Semester Registration",
                     "Contact the college office for registration dates."),
                    ("Library Reminder",
                     "Please return borrowed books on time.")
                ]
            )


def admin_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("login"))
        return function(*args, **kwargs)
    return wrapper


@app.route("/")
def dashboard():
    with get_db() as conn:
        total_students = conn.execute(
            "SELECT COUNT(*) FROM students"
        ).fetchone()[0]

        total_notices = conn.execute(
            "SELECT COUNT(*) FROM notices"
        ).fetchone()[0]

        recent_students = conn.execute(
            "SELECT * FROM students ORDER BY id DESC LIMIT 5"
        ).fetchall()

        notices = conn.execute(
            "SELECT * FROM notices ORDER BY id DESC LIMIT 4"
        ).fetchall()

    return render_template(
        "index.html",
        total_students=total_students,
        total_notices=total_notices,
        recent_students=recent_students,
        notices=notices
    )


@app.route("/students")
def students():
    q = request.args.get("q", "").strip()

    with get_db() as conn:
        if q:
            rows = conn.execute("""
                SELECT * FROM students
                WHERE name LIKE ? OR roll_no LIKE ?
                OR course LIKE ? OR semester LIKE ? OR email LIKE ?
                ORDER BY id DESC
            """, (
                f"%{q}%", f"%{q}%", f"%{q}%",
                f"%{q}%", f"%{q}%"
            )).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM students ORDER BY id DESC"
            ).fetchall()

    return render_template("students.html", students=rows, q=q)


# DELETE STUDENT (ADMIN ONLY)
@app.route("/students/<int:student_id>/delete", methods=["POST"])
@admin_required
def delete_student(student_id):
    with get_db() as conn:
        cursor = conn.execute(
            "DELETE FROM students WHERE id = ?",
            (student_id,)
        )

    if cursor.rowcount == 0:
        flash("Student record not found.", "error")
    else:
        flash("Student record deleted successfully.", "success")

    return redirect(url_for("students"))


# STUDENT REGISTRATION WITH SERVER-SIDE VALIDATION
@app.route("/students/add", methods=["GET", "POST"])
def add_student():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        roll_no = request.form.get("roll_no", "").strip()
        course = request.form.get("course", "").strip()
        semester = request.form.get("semester", "").strip()
        email = request.form.get("email", "").strip()

        errors = []

        if not re.fullmatch(r"[A-Za-z ]{2,50}", name):
            errors.append(
                "Invalid name. Use letters only (2–50 characters)."
            )

        if not re.fullmatch(r"[A-Za-z0-9-]{2,20}", roll_no):
            errors.append(
                "Invalid roll number. Use 2–20 letters, numbers or hyphens."
            )

        if email and not re.fullmatch(
            r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
            email
        ):
            errors.append("Invalid email format.")

        if course not in ["BCA", "BA", "BCom", "BSc"]:
            errors.append("Please select a valid course.")

        if semester not in ["1", "2", "3", "4", "5", "6"]:
            errors.append("Please select a valid semester.")

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("student_form.html")

        try:
            with get_db() as conn:
                conn.execute("""
                    INSERT INTO students
                    (name, roll_no, course, semester, email)
                    VALUES (?, ?, ?, ?, ?)
                """, (name, roll_no, course, semester, email))

            flash("Student registered successfully!", "success")
            return redirect(url_for("students"))

        except sqlite3.IntegrityError:
            flash("This roll number already exists.", "error")

        except sqlite3.Error:
            flash("Database error. Please try again.", "error")

    return render_template("student_form.html")


@app.route("/notices", methods=["GET", "POST"])
def notices_page():
    if request.method == "POST":
        if not session.get("admin_logged_in"):
            return redirect(url_for("login"))

        title = request.form.get("title", "").strip()
        details = request.form.get("details", "").strip()

        if title and details:
            with get_db() as conn:
                conn.execute(
                    "INSERT INTO notices (title, details) VALUES (?, ?)",
                    (title, details)
                )

            flash("Notice published successfully.", "success")
            return redirect(url_for("notices_page"))

        flash("Please enter title and details.", "error")

    with get_db() as conn:
        notices = conn.execute(
            "SELECT * FROM notices ORDER BY id DESC"
        ).fetchall()

    return render_template("notices.html", notices=notices)


@app.route("/notices/<int:notice_id>/delete", methods=["POST"])
@admin_required
def delete_notice(notice_id):
    with get_db() as conn:
        conn.execute(
            "DELETE FROM notices WHERE id = ?",
            (notice_id,)
        )

    flash("Notice deleted successfully.", "success")
    return redirect(url_for("notices_page"))


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        if not ADMIN_USERNAME or not ADMIN_PASSWORD:
            error = "Admin login is not configured yet."
        elif username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            return redirect(url_for("notices_page"))
        else:
            error = "Invalid username or password."

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("dashboard"))


@app.route("/about")
def about():
    return render_template("about.html")


init_db()


if __name__ == "__main__":
    app.run(debug=True)
