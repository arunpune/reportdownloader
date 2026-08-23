import os
import re
import sqlite3
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    send_file,
    abort,
)


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "test_reports.db"
STORAGE_DIR = BASE_DIR / "report_storage"

REPORTS_PER_PAGE = 100


# ============================================================
# FLASK APP
# ============================================================

app = Flask(__name__)

app.secret_key = os.getenv(
    "SECRET_KEY",
    "change-this-demo-secret"
)


# ============================================================
# DATABASE
# ============================================================

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ============================================================
# DATABASE MIGRATION
# ============================================================

def migrate_reports_table(conn):

    columns = conn.execute(
        "PRAGMA table_info(reports)"
    ).fetchall()

    column_names = [
        column["name"]
        for column in columns
    ]

    # --------------------------------------------------------
    # Old database had a "result" column.
    # Remove it if necessary.
    # --------------------------------------------------------

    if "result" in column_names:

        conn.executescript("""
            CREATE TABLE reports_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                iqube TEXT NOT NULL,
                report_date TEXT NOT NULL,
                serial_number TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                storage_path TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(customer_id, storage_path),
                FOREIGN KEY(customer_id) REFERENCES customers(id)
            );

            INSERT OR IGNORE INTO reports_new
                (
                    id,
                    customer_id,
                    iqube,
                    report_date,
                    serial_number,
                    original_filename,
                    storage_path,
                    created_at
                )
            SELECT
                id,
                customer_id,
                iqube,
                report_date,
                serial_number,
                original_filename,
                storage_path,
                created_at
            FROM reports;

            DROP TABLE reports;

            ALTER TABLE reports_new RENAME TO reports;
        """)

    # --------------------------------------------------------
    # Make sure indexes exist.
    # --------------------------------------------------------

    conn.executescript("""
        CREATE INDEX IF NOT EXISTS idx_reports_customer_date
            ON reports(customer_id, report_date);

        CREATE INDEX IF NOT EXISTS idx_reports_customer_serial
            ON reports(customer_id, serial_number);

        CREATE INDEX IF NOT EXISTS idx_reports_customer_iqube
            ON reports(customer_id, iqube);
    """)


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

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

    migrate_reports_table(conn)

    # Demo customer
    conn.execute(
        """
        INSERT OR IGNORE INTO customers
            (name, username, password)
        VALUES (?, ?, ?)
        """,
        (
            "Demo Customer",
            "tvs",
            "demo123"
        )
    )

    conn.commit()
    conn.close()


# ============================================================
# LOGIN
# ============================================================

def login_required(fn):

    @wraps(fn)
    def wrapper(*args, **kwargs):

        if "customer_id" not in session:
            return redirect(url_for("login"))

        return fn(*args, **kwargs)

    return wrapper


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():

    if "customer_id" in session:
        return redirect(url_for("reports"))

    return redirect(url_for("login"))


# ============================================================
# LOGIN PAGE
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    error = None

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        conn = db()

        customer = conn.execute(
            """
            SELECT *
            FROM customers
            WHERE username=?
            AND password=?
            """,
            (
                username,
                password
            )
        ).fetchone()

        conn.close()

        if customer:

            session["customer_id"] = customer["id"]

            session["customer_name"] = customer["name"]

            return redirect(
                url_for("reports")
            )

        error = "Invalid username or password."

    return render_template(
        "login.html",
        error=error
    )


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("login")
    )


# ============================================================
# EXTRACT TIME FROM ORIGINAL FILE NAME
# ============================================================

def extract_time(filename):

    """
    Extract time from filenames such as:

    I-QUBE-MLX90421_13-06-2026_22.37.26_13.xlsx

    Result:

    22:37:26
    """

    if not filename:
        return None

    # Look for:
    # HH.MM.SS
    # HH:MM:SS

    match = re.search(
        r"_(\d{2})[.:](\d{2})[.:](\d{2})_",
        filename
    )

    if match:

        hour = match.group(1)
        minute = match.group(2)
        second = match.group(3)

        return f"{hour}:{minute}:{second}"

    return None


# ============================================================
# REPORTS
# ============================================================

@app.route("/reports")
@login_required
def reports():

    # --------------------------------------------------------
    # Search filters
    # --------------------------------------------------------

    iqube = request.args.get(
        "iqube",
        ""
    ).strip()

    report_date = request.args.get(
        "date",
        ""
    ).strip()

    serial = request.args.get(
        "serial",
        ""
    ).strip()


    # --------------------------------------------------------
    # Pagination
    # --------------------------------------------------------

    try:

        page = int(
            request.args.get(
                "page",
                1
            )
        )

    except ValueError:

        page = 1


    if page < 1:
        page = 1


    offset = (
        page - 1
    ) * REPORTS_PER_PAGE


    # --------------------------------------------------------
    # Database connection
    # --------------------------------------------------------

    conn = db()


    # --------------------------------------------------------
    # Build WHERE clause
    # --------------------------------------------------------

    where_clause = """
        WHERE customer_id=?
    """

    params = [
        session["customer_id"]
    ]


    # Recipe filter
    if iqube:

        where_clause += """
            AND iqube=?
        """

        params.append(
            iqube
        )


    # Date filter
    if report_date:

        where_clause += """
            AND report_date=?
        """

        params.append(
            report_date
        )


    # Serial number filter
    if serial:

        where_clause += """
            AND serial_number LIKE ?
        """

        params.append(
            f"%{serial}%"
        )


    # --------------------------------------------------------
    # Count matching reports
    # --------------------------------------------------------

    count_query = f"""
        SELECT COUNT(*)
        FROM reports
        {where_clause}
    """

    total_reports = conn.execute(
        count_query,
        params
    ).fetchone()[0]


    # --------------------------------------------------------
    # Calculate pages
    # --------------------------------------------------------

    total_pages = max(
        1,
        (
            total_reports
            + REPORTS_PER_PAGE
            - 1
        )
        // REPORTS_PER_PAGE
    )


    if page > total_pages:

        page = total_pages

        offset = (
            page - 1
        ) * REPORTS_PER_PAGE


    # --------------------------------------------------------
    # Fetch reports
    # --------------------------------------------------------

    query = f"""
        SELECT
            id,
            iqube,
            report_date,
            serial_number,
            original_filename,
            storage_path
        FROM reports
        {where_clause}
        ORDER BY
            report_date DESC,
            id DESC
        LIMIT ?
        OFFSET ?
    """

    query_params = params + [
        REPORTS_PER_PAGE,
        offset
    ]


    rows = conn.execute(
        query,
        query_params
    ).fetchall()


    # --------------------------------------------------------
    # Prepare reports for template
    # --------------------------------------------------------

    reports_data = []

    for row in rows:

        report = dict(row)

        # Extract time from original filename
        report["report_time"] = extract_time(
            report["original_filename"]
        )

        reports_data.append(
            report
        )


    # --------------------------------------------------------
    # Recipe dropdown
    # --------------------------------------------------------

    iqubes = conn.execute(
        """
        SELECT DISTINCT iqube
        FROM reports
        WHERE customer_id=?
        ORDER BY iqube
        """,
        (
            session["customer_id"],
        )
    ).fetchall()


    conn.close()


    # --------------------------------------------------------
    # Date heading
    # --------------------------------------------------------

    if report_date:

        date_heading = report_date

    else:

        date_heading = "All Dates"


    # --------------------------------------------------------
    # Render
    # --------------------------------------------------------

    return render_template(
        "reports.html",

        reports=reports_data,

        iqubes=iqubes,

        filters={
            "iqube": iqube,
            "date": report_date,
            "serial": serial
        },

        customer_name=session.get(
            "customer_name"
        ),

        page=page,

        total_pages=total_pages,

        total_reports=total_reports,

        reports_per_page=REPORTS_PER_PAGE,

        date_heading=date_heading
    )


# ============================================================
# DOWNLOAD ORIGINAL REPORT
# ============================================================

@app.route("/download/<int:report_id>")
@login_required
def download(report_id):

    conn = db()

    row = conn.execute(
        """
        SELECT
            original_filename,
            storage_path
        FROM reports
        WHERE id=?
        AND customer_id=?
        """,
        (
            report_id,
            session["customer_id"]
        )
    ).fetchone()

    conn.close()


    if not row:
        abort(404)


    path = BASE_DIR / row["storage_path"]


    if not path.is_file():

        abort(
            404,
            "Original report file is missing from storage."
        )


    return send_file(
        path,
        as_attachment=True,
        download_name=row["original_filename"]
    )


# ============================================================
# START DATABASE
# ============================================================

init_db()


# ============================================================
# RUN SERVER
# ============================================================

if __name__ == "__main__":

    app.run(
        debug=True,
        port=5000
    )