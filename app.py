
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

        conn.execute("""
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                subject TEXT NOT NULL,
                max_marks INTEGER NOT NULL DEFAULT 100,
                obtained_marks INTEGER NOT NULL,
                FOREIGN KEY (student_id) REFERENCES students(id)
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
        conn.execute(
            "DELETE FROM results WHERE student_id = ?",
            (student_id,)
        )
        cursor = conn.execute(
            "DELETE FROM students WHERE id = ?",
            (student_id,)
        )

    if cursor.rowcount == 0:
        flash("Student record not found.", "error")
    else:
        flash("Student record deleted successfully.", "success")

    return redirect(url_for("students"))


# STUDENT REGISTRATION
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
            errors.append("Invalid name. Use letters only (2–50 characters).")

        if not re.fullmatch(r"[A-Za-z0-9-]{2,20}", roll_no):
            errors.append("Invalid roll number. Use 2–20 letters, numbers or hyphens.")

        if email and not re.fullmatch(
            r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", email
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


# MARKS AND RESULTS PAGE
@app.route("/results")
@admin_required
def results_page():
    with get_db() as conn:
        students_list = conn.execute(
            "SELECT * FROM students ORDER BY name"
        ).fetchall()

        result_rows = conn.execute("""
            SELECT results.*, students.name, students.roll_no
            FROM results
            JOIN students ON results.student_id = students.id
            ORDER BY students.name, results.subject
        """).fetchall()

    summaries = {}

    for row in result_rows:
        sid = row["student_id"]

        if sid not in summaries:
            summaries[sid] = {
                "name": row["name"],
                "roll_no": row["roll_no"],
                "total": 0,
                "obtained": 0,
                "count": 0,
                "failed": False
            }

        summaries[sid]["total"] += row["max_marks"]
        summaries[sid]["obtained"] += row["obtained_marks"]
        summaries[sid]["count"] += 1

        if row["obtained_marks"] < row["max_marks"] * 0.33:
            summaries[sid]["failed"] = True

    for summary in summaries.values():
        summary["percentage"] = round(
            summary["obtained"] / summary["total"] * 100, 2
        ) if summary["total"] else 0

        if summary["failed"]:
            summary["status"] = "Fail"
            summary["grade"] = "F"
        else:
            summary["status"] = "Pass"
            percentage = summary["percentage"]

            if percentage >= 80:
                summary["grade"] = "A"
            elif percentage >= 60:
                summary["grade"] = "B"
            elif percentage >= 45:
                summary["grade"] = "C"
            elif percentage >= 33:
                summary["grade"] = "D"
            else:
                summary["grade"] = "F"

    return render_template(
        "results.html",
        students=students_list,
        results=result_rows,
        summaries=summaries
    )


# ADD STUDENT MARKS (ADMIN ONLY)
@app.route("/results/add", methods=["POST"])
@admin_required
def add_result():
    student_id = request.form.get("student_id", type=int)
    subject = request.form.get("subject", "").strip()
    obtained_marks = request.form.get("obtained_marks", type=int)

    if not student_id or not subject or obtained_marks is None:
        flash("Please fill all result fields.", "error")
        return redirect(url_for("results_page"))

    if not re.fullmatch(r"[A-Za-z0-9 &()-]{2,60}", subject):
        flash("Please enter a valid subject name.", "error")
        return redirect(url_for("results_page"))

    if obtained_marks < 0 or obtained_marks > 100:
        flash("Marks must be between 0 and 100.", "error")
        return redirect(url_for("results_page"))

    with get_db() as conn:
        student = conn.execute(
            "SELECT id FROM students WHERE id = ?",
            (student_id,)
        ).fetchone()

        if not student:
            flash("Student not found.", "error")
            return redirect(url_for("results_page"))

        count = conn.execute(
            "SELECT COUNT(*) FROM results WHERE student_id = ?",
            (student_id,)
        ).fetchone()[0]

        if count >= 5:
            flash("This student already has 5 subject results.", "error")
            return redirect(url_for("results_page"))

        duplicate = conn.execute("""
            SELECT id FROM results
            WHERE student_id = ? AND LOWER(subject) = LOWER(?)
        """, (student_id, subject)).fetchone()

        if duplicate:
            flash("Marks for this subject already exist.", "error")
            return redirect(url_for("results_page"))

        conn.execute("""
            INSERT INTO results
            (student_id, subject, max_marks, obtained_marks)
            VALUES (?, ?, 100, ?)
        """, (student_id, subject, obtained_marks))

    flash("Marks added successfully.", "success")
    return redirect(url_for("results_page"))


# DELETE RESULT (ADMIN ONLY)
@app.route("/results/<int:result_id>/delete", methods=["POST"])
@admin_required
def delete_result(result_id):
    with get_db() as conn:
        cursor = conn.execute(
            "DELETE FROM results WHERE id = ?",
            (result_id,)
        )

    if cursor.rowcount:
        flash("Result deleted successfully.", "success")
    else:
        flash("Result not found.", "error")

    return redirect(url_for("results_page"))


# NOTICES
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


# ADMIN LOGIN
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
