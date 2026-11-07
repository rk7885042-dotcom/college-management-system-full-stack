from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from pathlib import Path

app = Flask(__name__)
app.secret_key = "change-this-secret-key"
DB_PATH = Path(__file__).with_name("college.db")

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
        count = conn.execute("SELECT COUNT(*) FROM notices").fetchone()[0]
        if count == 0:
            conn.executemany(
                "INSERT INTO notices (title, details) VALUES (?, ?)",
                [
                    ("Welcome to College Portal", "Use this demo portal to explore student records and college notices."),
                    ("Semester Registration", "Contact the college office for current semester registration dates."),
                    ("Library Reminder", "Please return borrowed books by their due date.")
                ]
            )

@app.route("/")
def dashboard():
    with get_db() as conn:
        total_students = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        total_notices = conn.execute("SELECT COUNT(*) FROM notices").fetchone()[0]
        recent_students = conn.execute("SELECT * FROM students ORDER BY id DESC LIMIT 5").fetchall()
        notices = conn.execute("SELECT * FROM notices ORDER BY id DESC LIMIT 4").fetchall()
    return render_template("index.html", total_students=total_students,
                           total_notices=total_notices,
                           recent_students=recent_students, notices=notices)

@app.route("/students")
def students():
    q = request.args.get("q", "").strip()
    with get_db() as conn:
        if q:
            rows = conn.execute(
                "SELECT * FROM students WHERE name LIKE ? OR roll_no LIKE ? OR course LIKE ? ORDER BY id DESC",
                (f"%{q}%", f"%{q}%", f"%{q}%")
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM students ORDER BY id DESC").fetchall()
    return render_template("students.html", students=rows, q=q)

@app.route("/students/add", methods=["GET", "POST"])
def add_student():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        roll_no = request.form.get("roll_no", "").strip()
        course = request.form.get("course", "").strip()
        semester = request.form.get("semester", "").strip()
        email = request.form.get("email", "").strip()
        if not all([name, roll_no, course, semester]):
            flash("Please fill in all required fields.", "error")
            return render_template("student_form.html")
        try:
            with get_db() as conn:
                conn.execute(
                    "INSERT INTO students (name, roll_no, course, semester, email) VALUES (?, ?, ?, ?, ?)",
                    (name, roll_no, course, semester, email)
                )
            flash("Student added successfully.", "success")
            return redirect(url_for("students"))
        except sqlite3.IntegrityError:
            flash("That roll number already exists. Please use a unique roll number.", "error")
    return render_template("student_form.html")

@app.route("/students/<int:student_id>/delete", methods=["POST"])
def delete_student(student_id):
    with get_db() as conn:
        conn.execute("DELETE FROM students WHERE id = ?", (student_id,))
    flash("Student record deleted.", "success")
    return redirect(url_for("students"))

@app.route("/notices", methods=["GET", "POST"])
def notices_page():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        details = request.form.get("details", "").strip()
        if title and details:
            with get_db() as conn:
                conn.execute("INSERT INTO notices (title, details) VALUES (?, ?)", (title, details))
            flash("Notice published.", "success")
            return redirect(url_for("notices_page"))
        flash("Enter both a title and notice details.", "error")
    with get_db() as conn:
        notices = conn.execute("SELECT * FROM notices ORDER BY id DESC").fetchall()
    return render_template("notices.html", notices=notices)

@app.route("/notices/<int:notice_id>/delete", methods=["POST"])
def delete_notice(notice_id):
    with get_db() as conn:
        conn.execute("DELETE FROM notices WHERE id = ?", (notice_id,))
    flash("Notice deleted.", "success")
    return redirect(url_for("notices_page"))

@app.route("/about")
def about():
    return render_template("about.html")

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
