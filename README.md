Suprajit Test Report Portal

A Flask + PostgreSQL web application for centralized discovery, controlled access, and secure download of LabVIEW-generated Excel test reports.

The portal is designed for multiple client companies such as TVS and Mahindra, with strict company-level isolation and support for multiple test recipes per company.

Users can search reports by:

Recipe

Date

Serial / Part Number

and download the original .xlsx workbook.

PostgreSQL stores authentication data and searchable report metadata only. The contents of the Excel workbook are not imported into PostgreSQL.

1. Project Status

This repository contains the current working development version of the client test-report portal.

The main end-to-end workflow is now:

LabVIEW / Client Test System
        ↓
Client report directory on the test PC
        ↓
Recipe folder detected
        ↓
Recipe → Company mapping from PostgreSQL
        ↓
Stable Excel report copied to portal archive
        ↓
Metadata stored in PostgreSQL
        ↓
Authenticated user logs into portal
        ↓
Company-authorized recipe selection
        ↓
Date / Serial search
        ↓
Matching report
        ↓
Secure download of original Excel workbook

The current development dataset contains TVS I-QUBE reports. Mahindra recipe mappings are configured so multi-recipe and cross-company access isolation can be tested even before real Mahindra reports are available.

2. Main Features

Authentication and Roles

The portal implements three roles:

SUPER_ADMIN

Can access reports from all companies.

Can access company administration.

Can access user administration.

Can create companies.

Can create users.

Can enable or disable companies.

Can enable or disable users.

Can reset user passwords.

COMPANY_ADMIN

Can access reports belonging only to their own company.

Can manage Company Users belonging to their own company.

Cannot access another company's reports.

Cannot manage Super Admin accounts.

Cannot manage Company Admin accounts outside the allowed scope.

COMPANY_USER

Can access reports belonging only to their own company.

Can search and download reports.

Has no administration access.

3. Authentication and Session Authorization

Passwords are stored using Argon2id password hashes and are never stored as plaintext.

Protected requests validate the logged-in user against PostgreSQL instead of trusting only previously stored session values.

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

If a user or company is disabled, an existing session cannot continue to provide authorized report access.

Super Admin accounts are not tied to a company.

4. Multi-Company and Multi-Recipe Design

A company can own more than one recipe.

Example:

TVS
└── I-QUBE-MLX90421

MAHINDRA
├── MAHINDRA-A301
└── MAHINDRA-KONEM

The database stores each recipe as a separate record associated with a company.

This prevents the application from guessing company ownership from recipe text or filenames.

The core relationship is:

Company
   ↓
Recipe
   ↓
Report

Each report therefore belongs to:

one company

one recipe

one original Excel file

5. Company Isolation

Company isolation is enforced on the server, not only in the user interface.

For a normal company user:

Logged-in user's company_id
        ↓
Allowed Recipes
        ↓
Allowed Reports

A TVS user can see only TVS recipes and TVS reports.

A Mahindra user can see only Mahindra recipes and Mahindra reports.

Even if a user manually changes a recipe ID or report ID in the URL, the backend validates that the requested object belongs to the user's company.

For example:

TVS user
    ↓
Requests Mahindra recipe ID
    ↓
Recipe filtered by TVS company_id
    ↓
No authorized match
    ↓
Request rejected

The download route applies the same company-scoped report query before returning a file.

6. PostgreSQL Data Model

The main tables are:

companies
users
recipes
reports
audit_logs

companies

Stores client organizations.

Important fields include:

id

name

code

is_active

created_at

Example company codes:

TVS
MAHINDRA

users

Stores:

email

Argon2id password hash

role

company association

active/inactive status

password-change requirement

last login time

creation timestamp

Roles:

SUPER_ADMIN
COMPANY_ADMIN
COMPANY_USER

recipes

Stores the recipes available to each company.

Important fields include:

id

company_id

name

folder_name

is_active

created_at

Example mappings:

I-QUBE-MLX90421 → TVS
MAHINDRA-A301   → MAHINDRA
MAHINDRA-KONEM  → MAHINDRA

folder_name is the exact folder name used in the client report directory.

The recipe table is now the source of truth for determining which company owns a report.

reports

Stores searchable metadata for each original Excel report.

Important fields include:

company_id

recipe_id

recipe_name

report_date

report_time

serial_number

original_filename

storage_path

created_at

The Excel workbook contents are not stored in PostgreSQL.

audit_logs

Stores security and activity events.

Typical fields include:

user

company

action

target type

target ID

IP address

structured details

timestamp

Audit logging can be used for events such as login and report-access activity.

7. Database Migrations

The project uses Flask-Migrate / Alembic for schema changes.

Migration files are stored under:

migrations/
└── versions/

Recent schema work includes:

audit log support

creation of the recipes table

addition of recipe_id to reports

Typical migration commands:

python -m flask db current
python -m flask db migrate -m "migration description"
python -m flask db upgrade

Migration files should be committed to Git so every developer and deployment can reproduce the same database schema.

8. Client Report Source Folder

The application now reads reports from the actual client-style report directory instead of requiring manual placement into a project-side watched folder.

The source root is configured using:

SOURCE_REPORT_ROOT="D:/path/to/REPORTS/EXCEL/SINGLE DUT REPORT"

Example development path:

D:\KONEM\BUILDS\TPS EOL - MLX90421\REPORTS\EXCEL\SINGLE DUT REPORT

The application scans from SINGLE DUT REPORT so multiple recipe folders can be discovered automatically.

Example:

SINGLE DUT REPORT
│
├── I-QUBE-MLX90421
│   ├── PASS
│   │   └── 13-06-2026
│   │       └── *.xlsx
│   └── FAIL
│
├── MAHINDRA-A301
│   ├── PASS
│   └── FAIL
│
└── MAHINDRA-KONEM
    ├── PASS
    └── FAIL

The first directory below SINGLE DUT REPORT is treated as the recipe folder.

9. Recipe-to-Company Mapping During Ingestion

Company ownership is no longer determined using a hard-coded default such as:

INGESTION_DEFAULT_COMPANY_CODE=TVS

That setting is obsolete for the multi-company design.

Instead:

Source file
    ↓
First folder below SOURCE_REPORT_ROOT
    ↓
Recipe.folder_name lookup
    ↓
Recipe.company_id
    ↓
Correct company

Example:

I-QUBE-MLX90421
    ↓
recipes.folder_name
    ↓
TVS

and:

MAHINDRA-A301
    ↓
recipes.folder_name
    ↓
MAHINDRA

Unknown/unconfigured recipe folders are skipped rather than being assigned to a default company.

10. Excel Filename Metadata

The ingestion service extracts searchable report metadata from filenames.

Expected format:

RECIPE_DD-MM-YYYY_HH.MM.SS_SERIAL.xlsx

Example:

I-QUBE-MLX90421_13-06-2026_22.33.21_12.xlsx

Extracted metadata:

Filename Recipe : I-QUBE-MLX90421
Date            : 13-06-2026
Time            : 22:33:21
Serial Number   : 12

Serial numbers remain strings so values such as:

01
03
05

retain their leading zeros.

The authoritative company/recipe relationship comes from the recipe folder and Recipe table, not from the filename alone.

11. File Stability Check

The ingestion service checks that a report is stable before copying it.

It compares file size and modification time, waits for the configured stability period, and verifies that the file has not changed.

This reduces the risk of copying a workbook while LabVIEW is still writing it.

Configuration:

FILE_STABILITY_SECONDS=2

12. Portal Archive (report_storage)

Reports discovered in the client source directory are copied to a portal-controlled archive.

Example:

Source:
SINGLE DUT REPORT/
└── I-QUBE-MLX90421/
    └── PASS/
        └── 13-06-2026/
            └── report.xlsx

Portal archive:
report_storage/
└── TVS/
    └── I-QUBE-MLX90421/
        └── PASS/
            └── 13-06-2026/
                └── report.xlsx

The original client/LabVIEW file remains untouched.

report_storage provides a stable application-controlled copy for customer downloads.

A second copy on the same physical drive is not a complete disaster-recovery backup. A real backup should be stored on separate physical or network storage.

Actual report files under report_storage should not be committed to GitHub.

13. Report Ingestion Flow

For each supported Excel report:

Detect report in SOURCE_REPORT_ROOT
        ↓
Ignore temporary / unsupported files
        ↓
Check file stability
        ↓
Read recipe folder
        ↓
Find active Recipe in PostgreSQL
        ↓
Determine company from Recipe.company_id
        ↓
Extract date / time / serial from filename
        ↓
Create portal archive destination
        ↓
Copy original Excel with shutil.copy2()
        ↓
Create or update Report metadata
        ↓
Commit to PostgreSQL

Repeated scans do not intentionally create a new row for the same stored report path.

14. Original Excel Preservation

The portal does not reconstruct or convert the workbook before download.

The copied file remains the original .xlsx report and therefore preserves its existing:

worksheets

rows and columns

formulas

formatting

charts

drawings

screenshots

embedded images

Browser-based Excel preview is not part of the current implementation.

15. Report Search

The report page supports:

Recipe
Date
Serial / Part Number

The Recipe dropdown now reads directly from the recipes table.

For a TVS user:

All recipes
I-QUBE-MLX90421

For a Mahindra user:

All recipes
MAHINDRA-A301
MAHINDRA-KONEM

All recipes means all recipes belonging to the logged-in user's company, not all recipes in the system.

The selected recipe is sent by recipe ID and validated by the backend before report filtering occurs.

16. Date Behaviour

By default, the report page displays reports for the previous day.

Example:

Current date: 02 September 2026
Default report date: 01 September 2026

The user can select another date through the date filter.

An informational processing message is shown for the default reporting period to indicate the report-processing schedule.

17. Secure Download

The portal never exposes the report-storage directory directly.

A download request is processed through Flask:

User requests report
        ↓
Authentication checked
        ↓
Company-scoped report query
        ↓
Requested report authorized?
        ↓
Resolve controlled storage path
        ↓
Path traversal protection
        ↓
Return original Excel file

A company user cannot retrieve another company's report simply by changing the report ID in the URL.

18. Current UI

The current interface includes:

Bootstrap-based responsive design

login page

report search page

recipe dropdown

date filter

serial-number filter

report count

pagination

secure Excel download

administration pages

current date in the navigation bar

logged-in user email

logout control

dynamic report heading

processing-status message

19. Project Structure

The current application is organized around the Flask app/ package.

Client_Test_Portal/
│
├── app/
│   ├── __init__.py
│   ├── admin.py
│   ├── audit.py
│   ├── auth.py
│   ├── cli.py
│   ├── config.py
│   ├── decorators.py
│   ├── extensions.py
│   ├── ingestion.py
│   ├── models.py
│   ├── reports.py
│   │
│   ├── templates/
│   │   ├── base.html
│   │   ├── login.html
│   │   ├── reports.html
│   │   ├── admin_dashboard.html
│   │   ├── companies.html
│   │   ├── change_password.html
│   │   └── ...
│   │
│   └── static/
│       └── css/
│           └── app.css
│
├── migrations/
│   └── versions/
│
├── deploy/
├── docs/
├── scripts/
├── tests/
├── report_storage/
│
├── run.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md

Legacy prototype folders such as the old root-level application, watched_folder, and other superseded scaffold directories are not part of the current architecture.

20. Important Files

app/__init__.py

Creates and configures the Flask application, initializes extensions, and registers application routes/blueprints.

app/config.py

Loads .env configuration including:

application name

Flask secret key

PostgreSQL connection

source report root

portal report storage

pagination

ingestion timing

session configuration

demo configuration

app/models.py

Defines:

Company
User
Recipe
Report
AuditLog

app/auth.py

Handles login, password verification, user/company validation, session creation, password-related flow, and logout.

app/reports.py

Handles:

company-scoped report access

company-scoped recipe access

recipe ID validation

date filtering

serial-number filtering

pagination

report headings

secure downloads

app/ingestion.py

Handles:

recursive scanning of SOURCE_REPORT_ROOT

stable-file checking

filename validation

recipe-folder detection

Recipe-to-Company lookup

archive copy creation

metadata insertion/update in PostgreSQL

one-time and continuous ingestion modes

app/admin.py

Handles company and user administration according to role-based permissions.

app/audit.py

Supports structured activity/audit logging.

21. Environment Configuration

Create a local .env using .env.example as a template.

Example:

# -----------------------------
# Application
# -----------------------------
APP_NAME="Suprajit Report Portal"
SECRET_KEY=replace-with-a-strong-secret
HOST=127.0.0.1
PORT=5000
DEBUG=true

# -----------------------------
# PostgreSQL
# -----------------------------
DATABASE_URL=postgresql+psycopg://USERNAME:PASSWORD@localhost:5432/test_reports

# -----------------------------
# Report source / storage
# -----------------------------
SOURCE_REPORT_ROOT="D:/path/to/REPORTS/EXCEL/SINGLE DUT REPORT"
STORAGE_DIR=report_storage

# -----------------------------
# Ingestion
# -----------------------------
FILE_STABILITY_SECONDS=2
INGESTION_POLL_SECONDS=2
ALLOWED_REPORT_EXTENSIONS=.xlsx

# -----------------------------
# Reports UI
# -----------------------------
REPORTS_PER_PAGE=100

# -----------------------------
# Session / security
# -----------------------------
SESSION_COOKIE_SECURE=false
SESSION_COOKIE_HTTPONLY=true
SESSION_COOKIE_SAMESITE=Lax
PERMANENT_SESSION_LIFETIME_SECONDS=28800

# -----------------------------
# Demo setup
# -----------------------------
SEED_DEMO_DATA=true
DEMO_COMPANY_NAME=TVS Motor
DEMO_COMPANY_CODE=TVS
DEMO_ADMIN_EMAIL=admin@tvs-demo.local
DEMO_ADMIN_PASSWORD=replace-with-password
DEMO_USER_EMAIL=user@tvs-demo.local
DEMO_USER_PASSWORD=replace-with-password
DEMO_SUPER_ADMIN_EMAIL=superadmin@portal-demo.local
DEMO_SUPER_ADMIN_PASSWORD=replace-with-password

The PostgreSQL port can vary by installation.

22. Environment Security

Never commit the real .env file.

It may contain:

PostgreSQL credentials

Flask secret key

local filesystem paths

demo or bootstrap credentials

The repository should include:

.env.example

but not:

.env

Recommended .gitignore entries include:

.env
.venv/
__pycache__/
*.py[cod]
.DS_Store

report_storage/*
!report_storage/.gitkeep

Customer Excel files must not be committed to GitHub.

23. Local Setup — Windows

1. Create the PostgreSQL database

Example database name:

test_reports

2. Create a virtual environment

py -m venv .venv

Activate:

.\.venv\Scripts\Activate.ps1

3. Install dependencies

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

4. Configure .env

Copy .env.example to .env and update:

DATABASE_URL

SECRET_KEY

SOURCE_REPORT_ROOT

local security/demo configuration

5. Apply migrations

python -m flask db upgrade

24. Recipe Configuration

Before ingesting reports, every source recipe folder must have a matching active Recipe row in PostgreSQL.

Example:

Folder                    Company
-----------------------------------------
I-QUBE-MLX90421           TVS
MAHINDRA-A301             MAHINDRA
MAHINDRA-KONEM            MAHINDRA

An unknown source recipe folder is skipped safely until it is configured.

This prevents accidental assignment of a report to the wrong customer.

25. Start Report Ingestion

One-time scan

python -m app.ingestion --once

This:

scans the configured source root

processes stable supported reports

copies them to the portal archive

creates/updates PostgreSQL metadata

exits

Continuous monitoring

python -m app.ingestion

This periodically checks the configured source directory for new or changed reports.

The ingestion process should be run separately from the web application.

26. Start the Web Application

python run.py

Then open:

http://127.0.0.1:5000

or:

http://localhost:5000

27. Example Customer Workflow

Login
    ↓
Open Test Reports
    ↓
Select one of the recipes authorized for the user's company
    ↓
Select Date
    ↓
Optionally enter Serial / Part Number
    ↓
Search
    ↓
Matching reports appear
    ↓
Download original Excel

28. Audit Logging

The project includes an audit_logs table for security and activity history.

Audit records can capture information such as:

LOGIN_SUCCESS
USER_CREATED
REPORT_DOWNLOADED

along with:

user

company

target object

IP address

timestamp

structured details

Audit logs are retained independently of report workbook contents.

29. Current Implemented Scope

Implemented:

Flask

PostgreSQL

SQLAlchemy

Flask-Migrate / Alembic

Bootstrap

login authentication

Argon2id password hashing

Super Admin role

Company Admin role

Company User role

company-based access isolation

multiple recipes per company

Recipe database model

Recipe → Company mapping

recipe-based report association

active-user validation

active-company validation

report search

recipe filter

date filter

serial-number filter

pagination

original Excel download

real source-folder ingestion

stable-file checks

portal-controlled report archive

filename metadata extraction

audit-log database

administration pages

current date in the UI

processing-status message

secure download authorization

database migrations

30. Features Still Deferred / Future Work

Possible future work includes:

production deployment configuration

HTTPS and reverse proxy

containerization

separate physical/network backup storage

automated PostgreSQL backups

ingestion retry/failure queue

production monitoring and alerting

browser-based Excel preview

PASS/FAIL filtering in the UI

richer audit-log administration screens

large-scale retention policy

automated cleanup/archival policy

deployment as a Windows/Linux service

cloud or internet-accessible hosting

stronger production secrets management

additional automated integration/security tests

31. Production Considerations

For local development:

DEBUG=true
SESSION_COOKIE_SECURE=false
SEED_DEMO_DATA=true

For production these should be changed appropriately, for example:

DEBUG=false
SESSION_COOKIE_SECURE=true
SEED_DEMO_DATA=false

Production deployment should also use:

HTTPS

secure secret generation

restricted PostgreSQL permissions

non-demo credentials

protected environment variables

PostgreSQL backups

separate report backups

system/service monitoring

controlled filesystem permissions

32. Technology Stack

Component

Technology

Backend

Python

Web Framework

Flask

Database

PostgreSQL

ORM

Flask-SQLAlchemy / SQLAlchemy

Migrations

Flask-Migrate / Alembic

PostgreSQL Driver

Psycopg 3

Password Hashing

Argon2id

Forms / CSRF

Flask-WTF

Frontend

HTML, Bootstrap, CSS

Configuration

python-dotenv

Report Format

Microsoft Excel .xlsx

File Copy

Python shutil.copy2()

Deployment Configuration

Gunicorn

Source Control

Git / GitHub

33. Current Architecture

                   LabVIEW / Test System
                           │
                           │ creates Excel reports
                           ▼
              Client SOURCE_REPORT_ROOT
                           │
                           ▼
                  Ingestion Service
                           │
               ┌───────────┴───────────┐
               │                       │
               ▼                       ▼
      Recipe / metadata lookup     Copy original XLSX
               │                       │
               ▼                       ▼
           PostgreSQL             report_storage/
               │                       │
               └───────────┬───────────┘
                           │
                           ▼
                      Flask Portal
                           │
             ┌─────────────┼─────────────┐
             ▼             ▼             ▼
           Login         Search       Download
             │             │             │
             ▼             ▼             ▼
            RBAC      PostgreSQL     Original XLSX

The key design principles are:

PostgreSQL stores authentication, authorization, recipe mappings, audit information, and searchable report metadata.

The client-generated Excel workbook remains unchanged, while the portal uses a controlled archive copy for secure customer downloads.

Company ownership is determined by the Recipe table, enabling multiple recipes per customer while maintaining strict isolation between companies such as TVS and Mahindra.
