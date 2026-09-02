# Test Report Portal — PostgreSQL Prototype

A Flask-based prototype for centralized discovery and secure download of LabVIEW-generated Excel test reports.

The portal allows authenticated users to search for a test report using:

* **Recipe Name**
* **Date**
* **Serial / Part Number**

and download the corresponding original Excel workbook.

The prototype uses **PostgreSQL only for searchable metadata and authentication data**. The contents of the Excel workbook are **not imported into PostgreSQL**.

---

## 1. Project Status

This repository currently represents a **working prototype/demo**, not the final client deployment.

The present objective is to demonstrate the complete basic workflow:

```text
User Login
    ↓
Recipe Selection
    ↓
Date Selection
    ↓
Serial / Part Number
    ↓
Search
    ↓
Matching Test Report
    ↓
Download Original Excel File
```

The prototype currently supports the supplied TVS test-report dataset and has been tested with **17 report records**.

---

# 2. Main Features

## Authentication

The portal implements three user roles:

### Super Admin

* Can access reports from all companies.
* Can access company administration.
* Can access user administration.
* Can create companies.
* Can create users.
* Can enable or disable companies.
* Can enable or disable users.
* Can reset user passwords.

### Company Admin

* Can access reports belonging only to their own company.
* Can manage Company Users belonging to their own company.
* Cannot access reports belonging to another company.
* Cannot manage Super Admin accounts.
* Cannot manage Company Admin accounts.

### Company User

* Can access reports belonging only to their own company.
* Can search and download reports.
* Has no administration access.

---

# 3. Authentication and Session Authorization

Passwords are stored using **Argon2id password hashes** and are never stored as plaintext.

After login, protected requests validate the user against PostgreSQL again.

The application verifies:

```text
Session contains user ID
        ↓
Load current user from PostgreSQL
        ↓
Does the user still exist?
        ↓
Is the user active?
        ↓
Is the user's company active?
        ↓
Use current role and company
        ↓
Allow or reject request
```

This means that if a Super Admin disables:

* a user account, or
* an entire company,

an existing logged-in session will no longer continue to provide report access.

Super Admin accounts are not tied to a company.

---

# 4. PostgreSQL Usage

PostgreSQL stores application metadata only.

The main database tables are:

```text
companies
users
reports
```

## `companies`

Stores information about organizations using the portal.

Example:

```text
TVS Motor
```

Important fields include:

* company ID
* company name
* company code
* active/inactive status

---

## `users`

Stores:

* email
* Argon2id password hash
* user role
* company association
* active/inactive status

Roles currently used:

```text
SUPER_ADMIN
COMPANY_ADMIN
COMPANY_USER
```

---

## `reports`

Stores metadata extracted from the Excel filename.

Typical values include:

* company
* recipe name
* report date
* report time
* serial number
* original filename
* stored-file path
* creation timestamp

The hundreds of rows, images, charts and worksheets inside the Excel workbook are **not stored in PostgreSQL**.

---

# 5. Excel Report Handling

The ingestion service does **not open or parse the Excel workbook**.

It does not use:

```text
pandas.read_excel()
openpyxl.load_workbook()
```

or any equivalent workbook-content parser.

Instead, it reads metadata from the filename.

Example:

```text
I-QUBE-MLX90421_13-06-2026_22.33.21_12.xlsx
```

Metadata extracted:

```text
Recipe Name   : I-QUBE-MLX90421
Date          : 13-06-2026
Time          : 22:33:21
Serial Number : 12
```

For the current interface, the recipe may be displayed in simplified form:

```text
Stored Recipe:
I-QUBE-MLX90421

Displayed Recipe:
I-QUBE
```

---

# 6. Original Excel File Preservation

After ingestion, the original `.xlsx` report is copied to the report-storage directory.

The workbook is not reconstructed or converted before download.

Therefore the downloaded workbook preserves the original:

* worksheets
* rows
* columns
* formulas
* formatting
* graphs
* drawings
* screenshots
* embedded images

The supplied test workbooks contain the following three worksheets:

```text
REPORT
TORQUE
SCREENSHOT
```

The website currently provides **download of the original Excel workbook**.

Browser-based Excel preview is not part of the current prototype.

---

# 7. Report Search

The report page provides three main filters:

```text
Recipe Name
Date
Serial Number
```

Example:

```text
Recipe Name : I-QUBE
Date        : 13-06-2026
Serial No   : 21
```

The portal searches PostgreSQL metadata and returns the matching report.

The page heading also reflects the selected report.

Example:

```text
Test report for 13-06-2026 · Serial No: 21
```

If only a date is selected:

```text
Test reports for 13-06-2026
```

If no date or serial number is selected:

```text
All test reports for all dates
```

---

# 8. Current UI Improvements

The current prototype includes:

* Bootstrap-based responsive interface
* Login page
* Report search page
* Report count
* Pagination
* Original Excel download
* Administration pages
* Current date displayed in the navigation bar
* Logged-in user email displayed in the navigation bar
* Dynamic report heading based on search filters

Example navigation bar:

```text
26 August 2026    user@tvs-demo.local    Logout
```

Admin users additionally receive administration navigation options.

---

# 9. Filename Format

The current ingestion engine expects filenames similar to:

```text
RECIPE-MODEL_DD-MM-YYYY_HH.MM.SS_SERIAL.xlsx
```

Example:

```text
I-QUBE-MLX90421_13-06-2026_22.33.21_12.xlsx
```

Another example with a leading-zero serial number:

```text
I-QUBE-MLX90421_13-06-2026_23.56.49_01.xlsx
```

Serial numbers are stored as strings so values such as:

```text
01
03
```

remain unchanged instead of becoming:

```text
1
3
```

---

# 10. Project Structure

```text
test_report_portal_postgres/
│
├── app/
│   │
│   ├── __init__.py
│   ├── config.py
│   ├── extensions.py
│   ├── models.py
│   ├── decorators.py
│   ├── auth.py
│   ├── reports.py
│   ├── admin.py
│   ├── cli.py
│   ├── ingestion.py
│   │
│   ├── templates/
│   │   ├── base.html
│   │   ├── login.html
│   │   ├── reports.html
│   │   ├── admin_dashboard.html
│   │   ├── companies.html
│   │   ├── company_form.html
│   │   ├── users.html
│   │   └── user_form.html
│   │
│   └── static/
│       └── css/
│           └── app.css
│
├── deploy/
│   └── gunicorn.conf.py
│
├── watched_folder/
│   └── TVS/
│       └── *.xlsx
│
├── report_storage/
│   └── TVS/
│
├── run.py
├── seed.py
├── requirements.txt
├── .env
├── .env.example
├── .gitignore
└── README.md
```

---

# 11. Important Files

## `app/__init__.py`

Application factory responsible for:

* creating the Flask application
* loading configuration
* creating required folders
* connecting SQLAlchemy
* enabling CSRF protection
* registering blueprints
* registering CLI commands
* creating missing prototype database tables

---

## `app/config.py`

Loads configuration from `.env`.

Controls:

* PostgreSQL connection
* Flask secret key
* host and port
* watched folder
* report storage folder
* pagination
* ingestion timing
* session configuration
* demo-data settings

---

## `app/models.py`

Defines PostgreSQL models for:

```text
Company
User
Report
```

---

## `app/auth.py`

Handles:

* login
* password verification
* active-user validation
* active-company validation
* session creation
* logout

---

## `app/decorators.py`

Contains reusable authentication and authorization helpers.

Protected requests check the current PostgreSQL user instead of trusting only previously stored session information.

---

## `app/reports.py`

Handles:

* report access control
* recipe filtering
* date filtering
* serial-number filtering
* pagination
* dynamic report headings
* secure Excel download

---

## `app/admin.py`

Handles administration functionality including:

* dashboard statistics
* user creation
* user enable/disable
* password reset
* company creation
* company enable/disable
* role-based administration restrictions

---

## `app/ingestion.py`

Handles report ingestion.

Responsibilities include:

* scanning the watched folder
* checking file stability
* validating report filenames
* extracting filename metadata
* determining the company
* copying the original Excel file
* inserting/updating PostgreSQL report metadata

The workbook itself is not parsed.

---

## `app/cli.py`

Provides command-line setup utilities including:

* creating a Super Admin
* creating a company

CLI utilities can be retained for initial/bootstrap setup.

Normal portal usage occurs through the web interface.

---

## `deploy/gunicorn.conf.py`

Configuration for running the Flask application with Gunicorn during later Linux/server deployment.

It controls:

* server address
* server port
* worker count
* request timeout
* access logging
* error logging

It is not required when running the prototype locally using:

```bash
python run.py
```

---

# 12. Architecture

```text
             LabVIEW Test System
                     │
                     │ creates .xlsx reports
                     ▼
              watched_folder/
                     │
                     ▼
             Ingestion Service
                     │
          ┌──────────┴──────────┐
          │                     │
          ▼                     ▼
Read filename metadata     Copy original Excel
          │                     │
          ▼                     ▼
      PostgreSQL          report_storage/
          │                     │
          └──────────┬──────────┘
                     │
                     ▼
                Flask Portal
                     │
          ┌──────────┼───────────┐
          ▼          ▼           ▼
       Login       Search      Download
          │          │           │
          ▼          ▼           ▼
       RBAC      PostgreSQL   Original XLSX
```

---

# 13. Ingestion Flow

For a report:

```text
watched_folder/TVS/
I-QUBE-MLX90421_13-06-2026_22.33.21_12.xlsx
```

the ingestion service performs:

```text
Detect file
    ↓
Check that file is stable
    ↓
Validate filename
    ↓
Identify company = TVS
    ↓
Extract recipe/date/time/serial
    ↓
Store metadata in PostgreSQL
    ↓
Copy original Excel to report_storage
```

No worksheet content needs to be imported into the database.

---

# 14. Watched Folder Structure

For the current TVS demo:

```text
watched_folder/
└── TVS/
    ├── report1.xlsx
    ├── report2.xlsx
    ├── report3.xlsx
    └── ...
```

For multiple companies:

```text
watched_folder/
├── TVS/
│   └── *.xlsx
│
└── MAHINDRA/
    └── *.xlsx
```

The first directory can be treated as the company code.

---

# 15. Report Storage Structure

Reports are copied to organized storage.

Conceptually:

```text
report_storage/
└── TVS/
    └── I-QUBE-MLX90421/
        └── 2026-06-13/
            └── report.xlsx
```

The portal does not expose this directory directly.

Downloads are handled through Flask so authorization can be checked first.

---

# 16. Local Setup — Windows

## Step 1 — Install PostgreSQL

Create a PostgreSQL database named:

```text
test_reports
```

This can be created using pgAdmin.

---

## Step 2 — Create a Windows virtual environment

From the project location:

```powershell
py -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

The terminal should show:

```text
(.venv)
```

---

## Step 3 — Install dependencies

```powershell
python -m pip install --upgrade pip
```

Then:

```powershell
python -m pip install -r requirements.txt
```

---

# 17. Environment Configuration

Create:

```text
.env
```

using `.env.example` as a template.

Example:

```env
# =====================================================
# APPLICATION
# =====================================================

APP_NAME=Test Report Portal

HOST=127.0.0.1
PORT=5000

DEBUG=true


# =====================================================
# FLASK SECURITY
# =====================================================

SECRET_KEY=replace-with-your-own-secret-key


# =====================================================
# POSTGRESQL DATABASE
# =====================================================

DATABASE_URL=postgresql+psycopg://USERNAME:PASSWORD@localhost:POSTGRES_PORT/test_reports


# =====================================================
# REPORT FOLDERS
# =====================================================

WATCH_DIR=watched_folder
STORAGE_DIR=report_storage


# =====================================================
# REPORT PAGINATION
# =====================================================

REPORTS_PER_PAGE=100


# =====================================================
# INGESTION
# =====================================================

FILE_STABILITY_SECONDS=2
INGESTION_POLL_SECONDS=2

INGESTION_DEFAULT_COMPANY_CODE=TVS

ALLOWED_REPORT_EXTENSIONS=.xlsx


# =====================================================
# SESSION
# =====================================================

SESSION_COOKIE_SECURE=false
SESSION_COOKIE_HTTPONLY=true
SESSION_COOKIE_SAMESITE=Lax

PERMANENT_SESSION_LIFETIME_SECONDS=28800


# =====================================================
# DEMO DATA
# =====================================================

SEED_DEMO_DATA=true

DEMO_COMPANY_NAME=TVS Motor
DEMO_COMPANY_CODE=TVS

DEMO_ADMIN_EMAIL=admin@tvs-demo.local
DEMO_ADMIN_PASSWORD=replace-with-password

DEMO_USER_EMAIL=user@tvs-demo.local
DEMO_USER_PASSWORD=replace-with-password

DEMO_SUPER_ADMIN_EMAIL=superadmin@portal-demo.local
DEMO_SUPER_ADMIN_PASSWORD=replace-with-password
```

The PostgreSQL port may differ between installations.

For example:

```text
5432
5433
```

Use the port configured on the local PostgreSQL server.

---

# 18. Important `.env` Rule

Never upload `.env` to GitHub.

It contains information such as:

* PostgreSQL username
* PostgreSQL password
* Flask secret key
* demo credentials

The repository should contain:

```text
.env.example
```

but not the real:

```text
.env
```

Make sure `.gitignore` contains:

```gitignore
.env
.venv/
__pycache__/
*.pyc
.DS_Store
__MACOSX/
```

---

# 19. Initialize the Demo Database

Run:

```powershell
python seed.py
```

The script creates the configured demo company and demo accounts if they do not already exist.

The default configuration uses:

```text
Super Admin
Company Admin
Company User
```

Credentials come from `.env`.

---

# 20. Start Report Ingestion

## One-time scan

To process all files currently present in the watched folder:

```powershell
python -m app.ingestion --once
```

This is useful when initially loading the demo dataset.

---

## Continuous watcher

To continuously monitor the watched folder:

```powershell
python -m app.ingestion
```

The service periodically checks for newly created Excel reports.

---

# 21. Start the Web Application

Run:

```powershell
python run.py
```

Then open:

```text
http://127.0.0.1:5000
```

or:

```text
http://localhost:5000
```

---

# 22. Demo Workflow

A typical Company User flow is:

```text
Login
    ↓
Open Test Reports
    ↓
Recipe = I-QUBE
    ↓
Select Date
    ↓
Enter Serial Number
    ↓
Search
    ↓
Matching report appears
    ↓
Download Excel
```

Example:

```text
Recipe:
I-QUBE

Date:
13-06-2026

Serial Number:
21
```

Result:

```text
I-QUBE-MLX90421_13-06-2026_23.27.45_21.xlsx
```

---

# 23. Secure Report Access

Report access is filtered by `company_id`.

A Company User or Company Admin can query only:

```text
Report.company_id == logged-in user's company_id
```

Super Admin can access reports belonging to all companies.

The download endpoint performs another authorization check before returning the file.

This prevents users from directly changing a report ID in the URL to retrieve another company's report.

---

# 24. CSRF Protection

Flask-WTF CSRF protection is enabled for form submissions.

This helps protect actions such as:

* login
* account administration
* company administration
* status changes

from forged form requests.

---

# 25. Current Prototype Dataset

The current development/demo environment has been tested with:

```text
17 unique test reports
```

including serial numbers with leading zeros such as:

```text
01
03
```

The dataset includes reports across:

```text
13-06-2026
14-06-2026
```

---

# 26. Current Prototype Scope

Included:

* PostgreSQL
* Flask
* Bootstrap
* Login authentication
* Argon2id password hashing
* Super Admin
* Company Admin
* Company User
* Company-based report isolation
* Active-user validation
* Active-company validation
* Report search
* Recipe filter
* Date filter
* Serial-number filter
* Pagination
* Original Excel download
* File watcher
* Filename-only metadata extraction
* Stable-file check
* Admin routes/pages
* Current date in UI
* Dynamic search-result heading

---

# 27. Features Intentionally Not Included Yet

Because the current application is a prototype, the following are deferred:

* browser-based Excel preview
* PASS/FAIL filtering
* audit-log database
* detailed download-history tracking
* PostgreSQL migration framework
* retry/failure queue
* automated backup system
* production HTTPS configuration
* cloud hosting
* containerization
* advanced Super Admin control dashboard
* automated test suite
* production monitoring

These can be implemented during later development phases if required.

---

# 28. Future Development

Possible future improvements include:

```text
Super Admin Control Dashboard
    ↓
Manage Companies
Manage Users
Assign Roles
Change User Company
Reset Password
Enable / Disable Access
```

Other later improvements may include:

* Docker containerization
* deployment on an internet-accessible server
* HTTPS
* reverse proxy
* PostgreSQL backups
* report-storage backups
* ingestion retry tracking
* audit logging
* browser report preview
* Flask-Migrate / Alembic
* automated RBAC tests
* deployment monitoring

---

# 29. Deployment Notes

The current Flask development server is intended only for local prototype use.

For later Linux/server deployment, the repository includes:

```text
deploy/gunicorn.conf.py
```

Gunicorn configuration currently controls:

```text
bind address
worker count
request timeout
access logging
error logging
```

A future deployed architecture may use:

```text
Internet
   ↓
HTTPS / Reverse Proxy
   ↓
Gunicorn
   ↓
Flask Portal
   ↓
PostgreSQL + Report Storage
```

The ingestion engine should run as a separate long-running service.

---

# 30. Security Notes

For local development:

```env
DEBUG=true
SESSION_COOKIE_SECURE=false
```

For eventual production deployment these should be changed appropriately.

Production considerations include:

```env
DEBUG=false
SESSION_COOKIE_SECURE=true
```

along with:

* HTTPS
* secure secret keys
* restricted PostgreSQL permissions
* non-demo passwords
* no demo-data seeding
* protected environment variables
* database backups
* report backups

---

# 31. Technology Stack

| Component                | Technology                    |
| ------------------------ | ----------------------------- |
| Backend                  | Python                        |
| Web Framework            | Flask                         |
| Database                 | PostgreSQL                    |
| ORM                      | Flask-SQLAlchemy / SQLAlchemy |
| PostgreSQL Driver        | Psycopg 3                     |
| Password Hashing         | Argon2id                      |
| Forms / CSRF             | Flask-WTF                     |
| Frontend                 | HTML, Bootstrap, CSS          |
| Configuration            | python-dotenv                 |
| Report Format            | Microsoft Excel `.xlsx`       |
| Deployment Configuration | Gunicorn                      |
| Source Control           | Git / GitHub                  |

---

# 32. Prototype Summary

The current Test Report Portal demonstrates the following complete workflow:

```text
LabVIEW generates Excel
          ↓
Excel enters watched folder
          ↓
Filename metadata extracted
          ↓
Metadata stored in PostgreSQL
          ↓
Original Excel copied unchanged
          ↓
User logs into Flask portal
          ↓
Role and company access checked
          ↓
User searches Recipe + Date + Serial
          ↓
Matching report displayed
          ↓
Authorization checked again
          ↓
Original Excel downloaded
```

The main design principle of the prototype is:

> **PostgreSQL is used for authentication and searchable metadata, while the original LabVIEW Excel workbook remains the source of truth for the complete test report.**


