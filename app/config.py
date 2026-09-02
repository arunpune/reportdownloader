"""
Application configuration for the Test Report Portal.

This module:
- Loads environment variables from the .env file
- Configures the Flask application
- Stores PostgreSQL connection settings
- Defines the report-storage path
- Controls report pagination and ingestion timing
- Configures session and cookie security settings
- Stores demo company and demo user configuration

Most values can be changed through the .env file without
modifying the Python source code.
"""


import os
from pathlib import Path
from datetime import timedelta

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def env_int(name, default):
    try:
        return int(os.getenv(name, str(default)))

    except ValueError:
        return default

def env_path(name, default):
    value = os.getenv(name, default).strip()
    path = Path(value)

    if not path.is_absolute():
        path = BASE_DIR / path

    return str(path.resolve())


class Config:

    APP_NAME = os.getenv(
        "APP_NAME",
        "Test Report Portal"
    )

    SECRET_KEY = os.getenv(
        "SECRET_KEY",
        "dev-only-change-me"
    )

    HOST = os.getenv(
        "HOST",
        "127.0.0.1"
    )

    PORT = env_int(
        "PORT",
        5000
    )

    DEBUG = env_bool(
        "DEBUG",
        False
    )

    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/test_reports",
    )

    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    
    # Root folder where LabVIEW/client generates original reports.
    SOURCE_REPORT_ROOT = env_path(
        "SOURCE_REPORT_ROOT",
        "reports",
    )

    # Controlled copy of reports used by the portal.
    STORAGE_DIR = env_path(
        "STORAGE_DIR",
        "report_storage",
    )

    REPORTS_PER_PAGE = max(
        1,
        env_int(
            "REPORTS_PER_PAGE",
            100
        )
    )

    FILE_STABILITY_SECONDS = max(
        0,
        env_int(
            "FILE_STABILITY_SECONDS",
            2
        )
    )

    INGESTION_POLL_SECONDS = max(
        1,
        env_int(
            "INGESTION_POLL_SECONDS",
            2
        )
    )

    

    ALLOWED_REPORT_EXTENSIONS = {
        x.strip().lower()
        for x in os.getenv(
            "ALLOWED_REPORT_EXTENSIONS",
            ".xlsx"
        ).split(",")
        if x.strip()
    }

    SESSION_COOKIE_SECURE = env_bool(
        "SESSION_COOKIE_SECURE",
        False
    )

    SESSION_COOKIE_HTTPONLY = env_bool(
        "SESSION_COOKIE_HTTPONLY",
        True
    )

    SESSION_COOKIE_SAMESITE = os.getenv(
        "SESSION_COOKIE_SAMESITE",
        "Lax"
    )

    PERMANENT_SESSION_LIFETIME = timedelta(
        seconds=max(
            300,
            env_int(
                "PERMANENT_SESSION_LIFETIME_SECONDS",
                28800
            )
        )
    )

    SEED_DEMO_DATA = env_bool(
        "SEED_DEMO_DATA",
        True
    )

    DEMO_COMPANY_NAME = os.getenv(
        "DEMO_COMPANY_NAME",
        "TVS Motor"
    )

    DEMO_COMPANY_CODE = os.getenv(
        "DEMO_COMPANY_CODE",
        "TVS"
    )

    DEMO_ADMIN_EMAIL = os.getenv(
        "DEMO_ADMIN_EMAIL",
        "admin@tvs-demo.local"
    )

    DEMO_ADMIN_PASSWORD = os.getenv(
        "DEMO_ADMIN_PASSWORD",
        "ChangeMe123!"
    )

    DEMO_USER_EMAIL = os.getenv(
        "DEMO_USER_EMAIL",
        "user@tvs-demo.local"
    )

    DEMO_USER_PASSWORD = os.getenv(
        "DEMO_USER_PASSWORD",
        "ChangeMe123!"
    )

    DEMO_SUPER_ADMIN_EMAIL = os.getenv(
        "DEMO_SUPER_ADMIN_EMAIL",
        "superadmin@portal-demo.local"
    )

    DEMO_SUPER_ADMIN_PASSWORD = os.getenv(
        "DEMO_SUPER_ADMIN_PASSWORD",
        "ChangeMe123!"
    )