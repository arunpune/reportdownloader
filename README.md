# Test Report Portal — Clean Demo

A clean demo for the LabVIEW test-report workflow.

## Architecture

LabVIEW test rig
→ `watched_folder/`
→ `ingestion.py`
→ searchable SQLite metadata + original Excel in `report_storage/`
→ Flask portal
→ customer search + secure Excel download

The project contains **no sample Excel files and no sample report rows**.

## First run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open:

`http://127.0.0.1:5000`

Demo login:

- Customer ID: `tvs`
- Password: `demo123`

## Use real Excel reports

1. Put a real `.xlsx` report into `watched_folder/`.
2. Run the ingestion service in another terminal:

```bash
python ingestion.py
```

3. The service waits for the file to become stable, reads metadata, copies the untouched workbook to `report_storage/`, and creates a searchable database row.
4. Refresh the portal.

## Inspect a real Excel before mapping

Run:

```bash
python inspect_excel.py watched_folder/YOUR_FILE.xlsx
```

This prints sheet names and cell coordinates/values. Use it to verify the actual locations of:

- I-QUBE / Recipe
- Date / timestamp
- Serial number / barcode
- PASS/FAIL

The ingestion code currently tries to discover values next to common labels. If the real workbook uses a custom layout, update the mapping logic after inspecting an actual report. No cell locations are assumed by this clean project.

## Important

`seed_demo.py` is intentionally not included. The portal should be populated only by real Excel files placed into `watched_folder/`.

## Why SQLite in this demo?

SQLite keeps the local demonstration self-contained and requires no separate database server. The schema and SQL are deliberately simple so the same report metadata model can later be moved to PostgreSQL for the client deployment.
