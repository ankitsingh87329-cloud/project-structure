import sqlite3
import os
from werkzeug.security import generate_password_hash


# ==================================================
# DATABASE PATH
# ==================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

DATABASE_FILE = os.path.join(
    BASE_DIR,
    "attendance.db"
)


# ==================================================
# DATABASE CONNECTION
# ==================================================

def get_connection():

    conn = sqlite3.connect(
        DATABASE_FILE
    )

    conn.row_factory = sqlite3.Row

    conn.execute(
        "PRAGMA foreign_keys = ON"
    )

    return conn


# ==================================================
# CREATE TABLES
# ==================================================

def create_tables():

    conn = get_connection()

    try:

        # ==========================================
        # ADMIN TABLE
        # ==========================================

        conn.execute("""
            CREATE TABLE IF NOT EXISTS admins (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                username TEXT UNIQUE NOT NULL,

                password TEXT NOT NULL

            )
        """)


        # ==========================================
        # STUDENTS TABLE
        # ==========================================

        conn.execute("""
            CREATE TABLE IF NOT EXISTS students (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                roll_no TEXT UNIQUE NOT NULL,

                name TEXT NOT NULL,

                email TEXT NOT NULL,

                branch TEXT NOT NULL,

                created_at TEXT DEFAULT CURRENT_TIMESTAMP

            )
        """)


        # ==========================================
        # ATTENDANCE TABLE
        # ==========================================

        conn.execute("""
            CREATE TABLE IF NOT EXISTS attendance (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                student_id INTEGER NOT NULL,

                date TEXT NOT NULL,

                time TEXT NOT NULL,

                FOREIGN KEY(student_id)
                    REFERENCES students(id)
                    ON DELETE CASCADE,

                UNIQUE(student_id, date)

            )
        """)


        # ==========================================
        # DEFAULT ADMIN
        # ==========================================

        admin = conn.execute(
            """
            SELECT *
            FROM admins
            WHERE username = ?
            """,
            ("admin",)
        ).fetchone()


        # ==========================================
        # CREATE ADMIN IF NOT EXISTS
        # ==========================================

        if admin is None:

            password_hash = generate_password_hash(
                "admin123"
            )

            conn.execute(
                """
                INSERT INTO admins
                (
                    username,
                    password
                )
                VALUES (?, ?)
                """,
                (
                    "admin",
                    password_hash
                )
            )

            print(
                "Default admin created."
            )

        else:

            print(
                "Admin already exists."
            )


        # ==========================================
        # COMMIT
        # ==========================================

        conn.commit()

        print(
            "Database tables created successfully."
        )

    except Exception as e:

        conn.rollback()

        print(
            "Database error:",
            e
        )

        raise

    finally:

        conn.close()


# ==================================================
# RESET ADMIN PASSWORD
# ==================================================

def reset_admin_password():

    conn = get_connection()

    try:

        password_hash = generate_password_hash(
            "admin123"
        )

        admin = conn.execute(
            """
            SELECT *
            FROM admins
            WHERE username = ?
            """,
            ("admin",)
        ).fetchone()


        if admin:

            conn.execute(
                """
                UPDATE admins

                SET password = ?

                WHERE username = ?
                """,
                (
                    password_hash,
                    "admin"
                )
            )

            print(
                "Admin password reset successfully."
            )

        else:

            conn.execute(
                """
                INSERT INTO admins
                (
                    username,
                    password
                )
                VALUES (?, ?)
                """,
                (
                    "admin",
                    password_hash
                )
            )

            print(
                "Admin account created successfully."
            )


        conn.commit()

    except Exception as e:

        conn.rollback()

        print(
            "Password reset error:",
            e
        )

        raise

    finally:

        conn.close()


# ==================================================
# CHECK DATABASE
# ==================================================

def check_database():

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


        print()
        print("=" * 50)
        print("DATABASE CHECK")
        print("=" * 50)

        print(
            "Database:",
            DATABASE_FILE
        )

        print(
            "Admin Count:",
            admin_count
        )

        print(
            "Student Count:",
            student_count
        )

        print(
            "Attendance Count:",
            attendance_count
        )

        print(
            "Admins:",
            [
                admin["username"]
                for admin in admins
            ]
        )

        print("=" * 50)

    finally:

        conn.close()


# ==================================================
# MAIN
# ==================================================

if __name__ == "__main__":

    print()
    print("=" * 50)
    print("FACE ATTENDANCE SYSTEM")
    print("=" * 50)

    print(
        "Database:",
        DATABASE_FILE
    )

    create_tables()

    reset_admin_password()

    check_database()

    print()
    print("=" * 50)
    print("LOGIN DETAILS")
    print("=" * 50)

    print(
        "Username: admin"
    )

    print(
        "Password: admin123"
    )

    print("=" * 50)