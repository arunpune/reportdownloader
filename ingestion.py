"""
Background ingestion service.

Reads metadata directly from REAL LabVIEW-generated Excel filenames.

Expected filename format:
    RECIPE-MODEL_DD-MM-YYYY_HH.MM.SS_SERIAL.xlsx

Example:
    I-QUBE-MLX90421_13-06-2026_22.33.21_12.xlsx

The Excel workbook is NOT opened.

Responsibilities:
1. Watch watched_folder/ for new .xlsx files.
2. Wait until a file is stable.
3. Extract recipe, model, date, time, serial number and filename.
4. Copy the original Excel file to report_storage/.
5. Store searchable metadata in SQLite.

PostgreSQL migration will be done separately.
"""

import re
import shutil
import sqlite3
import time
from datetime import datetime
from pathlib import Path


# =========================================================
# CONFIGURATION
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

WATCH_DIR = BASE_DIR / "watched_folder"
STORAGE_DIR = BASE_DIR / "report_storage"
DB_PATH = BASE_DIR / "test_reports.db"

CUSTOMER_USERNAME = "tvs"

WATCH_DIR.mkdir(exist_ok=True)
STORAGE_DIR.mkdir(exist_ok=True)


# =========================================================
# DATABASE
# =========================================================

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_report_time_column(conn):
    """
    Add report_time to existing SQLite databases if it
    does not already exist.
    """

    columns = conn.execute(
        "PRAGMA table_info(reports)"
    ).fetchall()

    column_names = [column["name"] for column in columns]

    if "report_time" not in column_names:
        conn.execute(
            "ALTER TABLE reports ADD COLUMN report_time TEXT"
        )
        conn.commit()

        print("DATABASE | Added report_time column")


# =========================================================
# FILENAME METADATA EXTRACTION
# =========================================================

def extract_metadata(path):
    """
    Extract metadata ONLY from the filename.

    Example:

        I-QUBE-MLX90421_13-06-2026_22.33.21_12.xlsx

    Returns:

        recipe_name       -> I-QUBE
        model_name        -> MLX90421
        report_date       -> 2026-06-13
        report_time       -> 22:33:21
        serial            -> 12
        original_filename -> complete filename
    """

    filename = path.name
    stem = path.stem

    pattern = re.compile(
        r"^(?P<recipe_model>.+?)"
        r"_(?P<date>\d{2}-\d{2}-\d{4})"
        r"_(?P<time>\d{2}\.\d{2}\.\d{2})"
        r"_(?P<serial>[^_]+)$"
    )

    match = pattern.match(stem)

    if not match:
        raise ValueError(
            f"Filename does not match expected format: {filename}"
        )

    recipe_model = match.group("recipe_model").strip()
    raw_date = match.group("date")
    raw_time = match.group("time")
    serial = match.group("serial").strip()

    # -----------------------------------------------------
    # Separate recipe and model
    # -----------------------------------------------------

    recipe_name = recipe_model
    model_name = None

    if "-" in recipe_model:

        parts = recipe_model.rsplit("-", 1)

        possible_recipe = parts[0].strip()
        possible_model = parts[1].strip()

        if possible_recipe and possible_model:
            recipe_name = possible_recipe
            model_name = possible_model

    # -----------------------------------------------------
    # Parse date and time
    # -----------------------------------------------------

    try:

        report_datetime = datetime.strptime(
            f"{raw_date} {raw_time}",
            "%d-%m-%Y %H.%M.%S"
        )

    except ValueError as exc:

        raise ValueError(
            f"Invalid date/time in filename: {filename}"
        ) from exc

    return {
        "recipe_name": recipe_name,
        "model_name": model_name,
        "report_date": report_datetime.strftime("%Y-%m-%d"),
        "report_time": report_datetime.strftime("%H:%M:%S"),
        "serial": serial,
        "original_filename": filename,
    }


# =========================================================
# FILE STABILITY CHECK
# =========================================================

def stable(path, wait_seconds=2):
    """
    Make sure LabVIEW has finished writing the file
    before processing it.
    """

    if not path.exists():
        return False

    try:
        size_before = path.stat().st_size
    except FileNotFoundError:
        return False

    time.sleep(wait_seconds)

    if not path.exists():
        return False

    try:
        size_after = path.stat().st_size
    except FileNotFoundError:
        return False

    return size_before == size_after


# =========================================================
# CUSTOMER LOOKUP
# =========================================================

def get_customer_id():
    """
    Get customer ID from SQLite.
    """

    conn = get_connection()

    row = conn.execute(
        """
        SELECT id
        FROM customers
        WHERE username=?
        """,
        (CUSTOMER_USERNAME,)
    ).fetchone()

    conn.close()

    if not row:
        raise RuntimeError(
            "Customer 'tvs' not found. "
            "Start app.py once to initialize the database."
        )

    return row["id"]


# =========================================================
# INGEST FILE
# =========================================================

def ingest(path):
    """
    Process one Excel file.

    The Excel workbook itself is never opened.
    All metadata comes from the filename.
    """

    metadata = extract_metadata(path)

    print(
        f"PROCESSING | {metadata['original_filename']}"
    )

    cid = get_customer_id()

    # -----------------------------------------------------
    # Make sure database has report_time
    # -----------------------------------------------------

    conn = get_connection()

    ensure_report_time_column(conn)

    conn.close()

    # -----------------------------------------------------
    # Create storage directory
    # -----------------------------------------------------

    safe_recipe = re.sub(
        r"[^A-Za-z0-9_.-]",
        "_",
        metadata["recipe_name"]
    )

    destination_dir = (
        STORAGE_DIR
        / CUSTOMER_USERNAME
        / safe_recipe
        / metadata["report_date"]
    )

    destination_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    # -----------------------------------------------------
    # Copy original Excel file
    # -----------------------------------------------------

    destination = destination_dir / path.name

    if destination.resolve() != path.resolve():

        shutil.copy2(
            path,
            destination
        )

    relative_storage_path = destination.relative_to(BASE_DIR)

    # -----------------------------------------------------
    # Save metadata
    # -----------------------------------------------------

    conn = get_connection()

    # Check whether this exact file was already inserted
    existing = conn.execute(
        """
        SELECT id
        FROM reports
        WHERE customer_id=?
        AND storage_path=?
        """,
        (
            cid,
            str(relative_storage_path)
        )
    ).fetchone()

    if existing:

        # Update metadata if the record already exists
        conn.execute(
            """
            UPDATE reports
            SET
                iqube=?,
                report_date=?,
                report_time=?,
                serial_number=?,
                original_filename=?
            WHERE id=?
            """,
            (
                metadata["recipe_name"],
                metadata["report_date"],
                metadata["report_time"],
                metadata["serial"],
                metadata["original_filename"],
                existing["id"]
            )
        )

        print(
            f"UPDATED | "
            f"RECIPE={metadata['recipe_name']} | "
            f"DATE={metadata['report_date']} | "
            f"TIME={metadata['report_time']} | "
            f"SERIAL={metadata['serial']}"
        )

    else:

        conn.execute(
            """
            INSERT INTO reports
            (
                customer_id,
                iqube,
                report_date,
                report_time,
                serial_number,
                original_filename,
                storage_path
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cid,
                metadata["recipe_name"],
                metadata["report_date"],
                metadata["report_time"],
                metadata["serial"],
                metadata["original_filename"],
                str(relative_storage_path)
            )
        )

        print(
            f"INGESTED | "
            f"RECIPE={metadata['recipe_name']} | "
            f"MODEL={metadata['model_name'] or 'N/A'} | "
            f"DATE={metadata['report_date']} | "
            f"TIME={metadata['report_time']} | "
            f"SERIAL={metadata['serial']} | "
            f"FILE={metadata['original_filename']}"
        )

    conn.commit()
    conn.close()


# =========================================================
# MAIN WATCHER
# =========================================================

def main():

    print()
    print("=" * 60)
    print("TEST REPORT INGESTION SERVICE")
    print("=" * 60)
    print(f"Watching: {WATCH_DIR}")
    print(f"Database: {DB_PATH}")
    print(f"Storage:  {STORAGE_DIR}")
    print("=" * 60)
    print()

    processed = set()

    while True:

        files = list(WATCH_DIR.glob("*.xlsx"))

        for path in files:

            try:

                key = (
                    str(path.resolve()),
                    path.stat().st_mtime_ns,
                    path.stat().st_size
                )

            except FileNotFoundError:
                continue

            if key in processed:
                continue

            try:

                if stable(path):

                    ingest(path)

                    processed.add(key)

            except Exception as exc:

                print(
                    f"ERROR | {path.name} | {exc}"
                )

        time.sleep(2)


# =========================================================
# START SERVICE
# =========================================================

if __name__ == "__main__":
    main()