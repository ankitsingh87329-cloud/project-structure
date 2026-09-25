from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    Response
)

from database import get_connection, create_tables

from face_utils import (
    capture_faces,
    create_encodings,
    mark_attendance
)

from werkzeug.security import check_password_hash

from datetime import datetime

import os
import csv
import io
import shutil

from functools import wraps


# ============================================================
# FLASK CONFIGURATION
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static")
)

app.secret_key = "change_this_secret_key_123"


# ============================================================
# PATH CONFIGURATION
# ============================================================

DATASET_DIR = os.path.join(BASE_DIR, "dataset")
ENCODING_DIR = os.path.join(BASE_DIR, "encodings")
ENCODING_FILE = os.path.join(ENCODING_DIR, "encodings.pkl")

os.makedirs(DATASET_DIR, exist_ok=True)
os.makedirs(ENCODING_DIR, exist_ok=True)


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

try:
    create_tables()
    print("Database initialized successfully.")
except Exception as e:
    print("Database initialization error:", e)


# ============================================================
# LOGIN REQUIRED DECORATOR
# ============================================================

def login_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        if "admin_id" not in session:
            flash("Please login first.")
            return redirect(url_for("login"))

        return function(*args, **kwargs)

    return wrapper


# ============================================================
# LOGIN
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if "admin_id" in session:
        return redirect(url_for("index"))

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:

            flash("Username and password are required.")
            return redirect(url_for("login"))

        conn = get_connection()

        try:

            admin = conn.execute(
                """
                SELECT id, username, password
                FROM admins
                WHERE username = ?
                """,
                (username,)
            ).fetchone()

        except Exception as e:

            print("Login database error:", e)
            admin = None

        finally:

            conn.close()

        password_correct = False

        if admin:

            try:

                password_correct = check_password_hash(
                    admin["password"],
                    password
                )

            except Exception as e:

                print("Password check error:", e)
                password_correct = False

        if password_correct:

            session.clear()

            session["admin_id"] = admin["id"]
            session["username"] = admin["username"]

            flash("Login successful!")

            return redirect(url_for("index"))

        flash("Invalid username or password.")

        return redirect(url_for("login"))

    return render_template("login.html")


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    flash("You have been logged out.")

    return redirect(url_for("login"))


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/")
@login_required
def index():

    conn = get_connection()

    try:

        total_students = conn.execute(
            """
            SELECT COUNT(*)
            FROM students
            """
        ).fetchone()[0]

        today = datetime.now().strftime("%Y-%m-%d")

        present_today = conn.execute(
            """
            SELECT COUNT(DISTINCT student_id)
            FROM attendance
            WHERE date = ?
            """,
            (today,)
        ).fetchone()[0]

        absent_today = total_students - present_today

        if absent_today < 0:
            absent_today = 0

        total_attendance = conn.execute(
            """
            SELECT COUNT(*)
            FROM attendance
            """
        ).fetchone()[0]

        recent_attendance = conn.execute(
            """
            SELECT
                attendance.id,
                students.roll_no,
                students.name,
                students.branch,
                attendance.date,
                attendance.time
            FROM attendance
            JOIN students
            ON attendance.student_id = students.id
            ORDER BY
                attendance.date DESC,
                attendance.time DESC
            LIMIT 10
            """
        ).fetchall()

    finally:

        conn.close()

    return render_template(
        "dashboard.html",
        total_students=total_students,
        present_today=present_today,
        absent_today=absent_today,
        total_attendance=total_attendance,
        recent_attendance=recent_attendance,
        today=today
    )


# ============================================================
# REGISTER STUDENT
# ============================================================

@app.route("/register", methods=["GET", "POST"])
@login_required
def register():

    if request.method == "POST":

        roll_no = request.form.get(
            "roll_no", ""
        ).strip()

        name = request.form.get(
            "name", ""
        ).strip()

        email = request.form.get(
            "email", ""
        ).strip()

        branch = request.form.get(
            "branch", ""
        ).strip()

        if not roll_no or not name or not email or not branch:

            flash("Please fill all fields.")

            return redirect(url_for("register"))

        conn = get_connection()

        try:

            existing = conn.execute(
                """
                SELECT id
                FROM students
                WHERE roll_no = ?
                """,
                (roll_no,)
            ).fetchone()

            if existing:

                flash("Roll number already exists.")

                return redirect(url_for("register"))

            cursor = conn.execute(
                """
                INSERT INTO students
                (
                    roll_no,
                    name,
                    email,
                    branch
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    roll_no,
                    name,
                    email,
                    branch
                )
            )

            student_id = cursor.lastrowid

            conn.commit()

        except Exception as e:

            conn.rollback()

            flash(f"Student registration error: {e}")

            return redirect(url_for("register"))

        finally:

            conn.close()

        # Capture face
        try:

            success = capture_faces(student_id)

        except Exception as e:

            print("Face capture error:", e)
            success = False

        if not success:

            conn = get_connection()

            try:

                conn.execute(
                    """
                    DELETE FROM students
                    WHERE id = ?
                    """,
                    (student_id,)
                )

                conn.commit()

            finally:

                conn.close()

            student_folder = os.path.join(
                DATASET_DIR,
                str(student_id)
            )

            if os.path.exists(student_folder):

                try:
                    shutil.rmtree(student_folder)
                except Exception as e:
                    print("Folder delete error:", e)

            flash(
                "Face capture failed. "
                "Student registration cancelled."
            )

            return redirect(url_for("register"))

        # Create face encoding
        try:

            encoding_success = create_encodings()

        except Exception as e:

            print("Encoding error:", e)
            encoding_success = False

        if encoding_success:

            flash(
                "Student registered successfully."
            )

        else:

            flash(
                "Student registered, "
                "but face encoding failed."
            )

        return redirect(url_for("students"))

    return render_template("register.html")


# ============================================================
# STUDENTS LIST
# ============================================================

@app.route("/students")
@login_required
def students():

    search = request.args.get(
        "search",
        ""
    ).strip()

    conn = get_connection()

    try:

        if search:

            students_data = conn.execute(
                """
                SELECT *
                FROM students
                WHERE
                    roll_no LIKE ?
                    OR name LIKE ?
                    OR email LIKE ?
                    OR branch LIKE ?
                ORDER BY name
                """,
                (
                    f"%{search}%",
                    f"%{search}%",
                    f"%{search}%",
                    f"%{search}%"
                )
            ).fetchall()

        else:

            students_data = conn.execute(
                """
                SELECT *
                FROM students
                ORDER BY name
                """
            ).fetchall()

    finally:

        conn.close()

    return render_template(
        "students.html",
        students=students_data,
        search=search
    )


# ============================================================
# DELETE STUDENT
# ============================================================

@app.route(
    "/delete_student/<int:student_id>",
    methods=["POST"]
)
@login_required
def delete_student(student_id):

    conn = get_connection()

    try:

        student = conn.execute(
            """
            SELECT *
            FROM students
            WHERE id = ?
            """,
            (student_id,)
        ).fetchone()

        if student is None:

            flash("Student not found.")

            return redirect(url_for("students"))

        # Delete attendance first
        conn.execute(
            """
            DELETE FROM attendance
            WHERE student_id = ?
            """,
            (student_id,)
        )

        # Delete student
        conn.execute(
            """
            DELETE FROM students
            WHERE id = ?
            """,
            (student_id,)
        )

        conn.commit()

    except Exception as e:

        conn.rollback()

        flash(f"Delete error: {e}")

        return redirect(url_for("students"))

    finally:

        conn.close()

    # Delete face dataset
    student_folder = os.path.join(
        DATASET_DIR,
        str(student_id)
    )

    if os.path.exists(student_folder):

        try:

            shutil.rmtree(student_folder)

        except Exception as e:

            print("Dataset delete error:", e)

    # Recreate encodings
    try:

        create_encodings()

    except Exception as e:

        print("Encoding recreation error:", e)

    flash(
        f"{student['name']} deleted successfully."
    )

    return redirect(url_for("students"))


# ============================================================
# MARK ATTENDANCE
# ============================================================

@app.route("/attendance")
@login_required
def attendance():

    try:

        result = mark_attendance()

    except Exception as e:

        print("Attendance error:", e)

        flash(
            f"Attendance system error: {e}"
        )

        return redirect(
            url_for("attendance_records")
        )

    if result:

        flash(
            f"Attendance marked for {result}."
        )

    else:

        flash(
            "No attendance marked. "
            "Face may not be recognized "
            "or attendance may already exist."
        )

    return redirect(
        url_for("attendance_records")
    )


# ============================================================
# ATTENDANCE RECORDS
# ============================================================

@app.route("/records")
@login_required
def attendance_records():

    selected_date = request.args.get(
        "date",
        ""
    ).strip()

    conn = get_connection()

    try:

        if selected_date:

            records = conn.execute(
                """
                SELECT
                    attendance.id,
                    students.roll_no,
                    students.name,
                    students.branch,
                    students.email,
                    attendance.date,
                    attendance.time
                FROM attendance
                JOIN students
                ON attendance.student_id = students.id
                WHERE attendance.date = ?
                ORDER BY attendance.time DESC
                """,
                (selected_date,)
            ).fetchall()

        else:

            records = conn.execute(
                """
                SELECT
                    attendance.id,
                    students.roll_no,
                    students.name,
                    students.branch,
                    students.email,
                    attendance.date,
                    attendance.time
                FROM attendance
                JOIN students
                ON attendance.student_id = students.id
                ORDER BY
                    attendance.date DESC,
                    attendance.time DESC
                """
            ).fetchall()

    finally:

        conn.close()

    return render_template(
        "attendance.html",
        records=records,
        selected_date=selected_date
    )


# ============================================================
# DELETE ATTENDANCE
# ============================================================

@app.route(
    "/delete_attendance/<int:attendance_id>",
    methods=["POST"]
)
@login_required
def delete_attendance(attendance_id):

    conn = get_connection()

    try:

        record = conn.execute(
            """
            SELECT *
            FROM attendance
            WHERE id = ?
            """,
            (attendance_id,)
        ).fetchone()

        if record is None:

            flash(
                "Attendance record not found."
            )

        else:

            conn.execute(
                """
                DELETE FROM attendance
                WHERE id = ?
                """,
                (attendance_id,)
            )

            conn.commit()

            flash(
                "Attendance record deleted successfully."
            )

    except Exception as e:

        conn.rollback()

        flash(
            f"Delete attendance error: {e}"
        )

    finally:

        conn.close()

    return redirect(
        url_for("attendance_records")
    )


# ============================================================
# ATTENDANCE PERCENTAGE
# ============================================================

@app.route("/percentage")
@app.route("/attendance_percentage")
@login_required
def percentage():

    conn = get_connection()

    try:

        total_days = conn.execute(
            """
            SELECT COUNT(DISTINCT date)
            FROM attendance
            """
        ).fetchone()[0]

        students_data_db = conn.execute(
            """
            SELECT *
            FROM students
            ORDER BY name
            """
        ).fetchall()

        students_data = []

        for student in students_data_db:

            present_days = conn.execute(
                """
                SELECT COUNT(DISTINCT date)
                FROM attendance
                WHERE student_id = ?
                """,
                (student["id"],)
            ).fetchone()[0]

            if total_days > 0:

                attendance_percentage = (
                    present_days / total_days
                ) * 100

            else:

                attendance_percentage = 0

            students_data.append({
                "id": student["id"],
                "roll_no": student["roll_no"],
                "name": student["name"],
                "branch": student["branch"],
                "present_days": present_days,
                "total_days": total_days,
                "percentage": round(
                    attendance_percentage,
                    2
                )
            })

    finally:

        conn.close()

    return render_template(
        "attendance_percentage.html",
        data=students_data
    )


# ============================================================
# EXPORT ATTENDANCE CSV
# ============================================================

@app.route("/export_csv")
@app.route("/export_attendance")
@login_required
def export_csv():

    selected_date = request.args.get(
        "date",
        ""
    ).strip()

    conn = get_connection()

    try:

        if selected_date:

            records = conn.execute(
                """
                SELECT
                    students.roll_no,
                    students.name,
                    students.branch,
                    students.email,
                    attendance.date,
                    attendance.time
                FROM attendance
                JOIN students
                ON attendance.student_id = students.id
                WHERE attendance.date = ?
                ORDER BY attendance.time
                """,
                (selected_date,)
            ).fetchall()

        else:

            records = conn.execute(
                """
                SELECT
                    students.roll_no,
                    students.name,
                    students.branch,
                    students.email,
                    attendance.date,
                    attendance.time
                FROM attendance
                JOIN students
                ON attendance.student_id = students.id
                ORDER BY
                    attendance.date DESC,
                    attendance.time DESC
                """
            ).fetchall()

    finally:

        conn.close()

    output = io.StringIO()

    writer = csv.writer(output)

    writer.writerow([
        "Roll No",
        "Name",
        "Branch",
        "Email",
        "Date",
        "Time"
    ])

    for record in records:

        writer.writerow([
            record["roll_no"],
            record["name"],
            record["branch"],
            record["email"],
            record["date"],
            record["time"]
        ])

    csv_data = output.getvalue()

    output.close()

    filename = "attendance.csv"

    if selected_date:

        filename = f"attendance_{selected_date}.csv"

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={
            "Content-Disposition":
                f"attachment; filename={filename}"
        }
    )


# ============================================================
# TEST DATABASE
# ==========
@app.route("/test-db")
def test_db():

    conn = get_connection()

    try:

        admin_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM admins
            """
        ).fetchone()[0]

        student_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM students
            """
        ).fetchone()[0]

        attendance_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM attendance
            """
        ).fetchone()[0]

        admins = conn.execute(
            """
            SELECT username
            FROM admins
            """
        ).fetchall()

        admin_names = [
            row["username"]
            for row in admins
        ]

        return {
            "database": "OK",
            "admin_count": admin_count,
            "student_count": student_count,
            "attendance_count": attendance_count,
            "admins": admin_names
        }

    except Exception as e:

        return {
            "database": "ERROR",
            "error": str(e)
        }, 500

    finally:

        conn.close()


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/health")
def health():

    return {
        "status": "running",
        "application": "Face Attendance System"
    }


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def page_not_found(error):

    return """
    <h1>404 - Page Not Found</h1>
    <p>The requested page does not exist.</p>
    """, 404


@app.errorhandler(500)
def internal_server_error(error):

    return """
    <h1>500 - Internal Server Error</h1>
    <p>Check the VS Code terminal for the error.</p>
    """, 500


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("Face Attendance System")
    print("=" * 60)
    print("Login URL: http://127.0.0.1:5000/login")
    print("Test DB:   http://127.0.0.1:5000/test-db")
    print("Health:    http://127.0.0.1:5000/health")
    print("=" * 60)

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )