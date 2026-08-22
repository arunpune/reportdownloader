import os
import sqlite3
from functools import wraps
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, session, send_file, abort

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "test_reports.db"
STORAGE_DIR = BASE_DIR / "report_storage"

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change-this-demo-secret")


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        iqube TEXT NOT NULL,
        report_date TEXT NOT NULL,
        serial_number TEXT NOT NULL,
        result TEXT NOT NULL,
        original_filename TEXT NOT NULL,
        storage_path TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(customer_id, storage_path),
        FOREIGN KEY(customer_id) REFERENCES customers(id)
    );

    CREATE INDEX IF NOT EXISTS idx_reports_customer_date
        ON reports(customer_id, report_date);
    CREATE INDEX IF NOT EXISTS idx_reports_customer_serial
        ON reports(customer_id, serial_number);
    CREATE INDEX IF NOT EXISTS idx_reports_customer_iqube
        ON reports(customer_id, iqube);
    """)
    conn.execute(
        "INSERT OR IGNORE INTO customers(name, username, password) VALUES (?, ?, ?)",
        ("Demo Customer", "tvs", "demo123")
    )
    conn.commit()
    conn.close()


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "customer_id" not in session:
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper


@app.route("/")
def home():
    return redirect(url_for("reports") if "customer_id" in session else url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        conn = db()
        customer = conn.execute(
            "SELECT * FROM customers WHERE username=? AND password=?",
            (username, password)
        ).fetchone()
        conn.close()
        if customer:
            session["customer_id"] = customer["id"]
            session["customer_name"] = customer["name"]
            return redirect(url_for("reports"))
        error = "Invalid username or password."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/reports")
@login_required
def reports():
    iqube = request.args.get("iqube", "").strip()
    report_date = request.args.get("date", "").strip()
    serial = request.args.get("serial", "").strip()

    conn = db()
    query = """
        SELECT id, iqube, report_date, serial_number, result,
               original_filename
        FROM reports
        WHERE customer_id=?
    """
    params = [session["customer_id"]]

    if iqube:
        query += " AND iqube=?"
        params.append(iqube)
    if report_date:
        query += " AND report_date=?"
        params.append(report_date)
    if serial:
        query += " AND serial_number LIKE ?"
        params.append(f"%{serial}%")

    query += " ORDER BY report_date DESC, id DESC"
    rows = conn.execute(query, params).fetchall()

    iqubes = conn.execute(
        "SELECT DISTINCT iqube FROM reports WHERE customer_id=? ORDER BY iqube",
        (session["customer_id"],)
    ).fetchall()
    conn.close()

    return render_template(
        "reports.html",
        reports=rows,
        iqubes=iqubes,
        filters={"iqube": iqube, "date": report_date, "serial": serial},
        customer_name=session.get("customer_name")
    )


@app.route("/download/<int:report_id>")
@login_required
def download(report_id):
    conn = db()
    row = conn.execute(
        """SELECT original_filename, storage_path
           FROM reports
           WHERE id=? AND customer_id=?""",
        (report_id, session["customer_id"])
    ).fetchone()
    conn.close()

    if not row:
        abort(404)

    path = BASE_DIR / row["storage_path"]
    if not path.is_file():
        abort(404, "Original report file is missing from storage.")

    return send_file(path, as_attachment=True, download_name=row["original_filename"])


init_db()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
