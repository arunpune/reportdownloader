"""
PostgreSQL database models for the Test Report Portal.

Main tables:
- Company: customer/company information
- User: login accounts and role information
- Recipe: test recipes belonging to each company
- Report: metadata for each original Excel report
- AuditLog: security and activity audit records

The large Excel workbook contents are NOT stored in PostgreSQL.
Only searchable metadata and the stored file path are saved.
"""

from datetime import datetime, timezone

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError

from .extensions import db


password_hasher = PasswordHasher()


class Company(db.Model):
    __tablename__ = "companies"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    name = db.Column(
        db.String(150),
        nullable=False,
    )

    code = db.Column(
        db.String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    is_active = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    users = db.relationship(
        "User",
        back_populates="company",
        lazy=True,
    )

    reports = db.relationship(
        "Report",
        back_populates="company",
        lazy=True,
    )

    recipes = db.relationship(
    "Recipe",
    back_populates="company",
    lazy=True,
    )


class Recipe(db.Model):
    __tablename__ = "recipes"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    # Company/client that owns this recipe.
    company_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "companies.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    # User-friendly recipe name displayed in the portal.
    name = db.Column(
        db.String(150),
        nullable=False,
    )

    # Exact folder name present in the report directory.
    folder_name = db.Column(
        db.String(255),
        nullable=False,
    )

    # Allows a recipe to be disabled without deleting it.
    is_active = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    company = db.relationship(
        "Company",
        back_populates="recipes",
    )

    reports = db.relationship(
        "Report",
        back_populates="recipe",
        lazy=True,
    )

    __table_args__ = (
        # A company cannot have two recipes with the same name.
        db.UniqueConstraint(
            "company_id",
            "name",
            name="uq_recipes_company_name",
        ),

        # A company cannot map two recipes to the same physical folder.
        db.UniqueConstraint(
            "company_id",
            "folder_name",
            name="uq_recipes_company_folder",
        ),
    )


class User(db.Model):
    __tablename__ = "users"

    ROLE_SUPER_ADMIN = "SUPER_ADMIN"
    ROLE_COMPANY_ADMIN = "COMPANY_ADMIN"
    ROLE_COMPANY_USER = "COMPANY_USER"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    company_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "companies.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    email = db.Column(
        db.String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    password_hash = db.Column(
        db.String(512),
        nullable=False,
    )

    role = db.Column(
        db.String(30),
        nullable=False,
        index=True,
    )

    is_active = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
    )

    must_change_password = db.Column(
    db.Boolean,
    nullable=False,
    default=True,
    )

    last_login_at = db.Column(
    db.DateTime(timezone=True),
    nullable=True,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    company = db.relationship(
        "Company",
        back_populates="users",
    )

    def set_password(self, password):
        self.password_hash = password_hasher.hash(password)

    def check_password(self, password):
        try:
            return password_hasher.verify(
                self.password_hash,
                password,
            )
        except (
            VerifyMismatchError,
            VerificationError,
        ):
            return False

    @property
    def is_super_admin(self):
        return self.role == self.ROLE_SUPER_ADMIN


class Report(db.Model):
    __tablename__ = "reports"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    # Every report belongs to a specific client company.
    company_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "companies.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # Recipe to which this report belongs.
    #
    # Nullable temporarily because existing reports do not yet
    # have recipe_id values. After backfilling old reports,
    # this can be changed to nullable=False.
    recipe_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "recipes.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
        index=True,
    )

    # Recipe name from the test report.
    recipe_name = db.Column(
        db.String(150),
        nullable=False,
        index=True,
    )

    # Date of the test report.
    report_date = db.Column(
        db.Date,
        nullable=False,
        index=True,
    )

    # Time of the test report.
    report_time = db.Column(
        db.Time,
        nullable=True,
    )

    # Actual serial number from the report/file.
    #
    # This MUST remain a String because values such as:
    # 03
    # 05
    # 13
    # must retain their leading zeros.
    serial_number = db.Column(
        db.String(255),
        nullable=False,
        index=True,
    )

    # Original Excel filename.
    original_filename = db.Column(
        db.String(500),
        nullable=False,
    )

    # Relative path to the stored original Excel file.
    storage_path = db.Column(
        db.String(1000),
        nullable=False,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    company = db.relationship(
        "Company",
        back_populates="reports",
    )

    recipe = db.relationship(
    "Recipe",
    back_populates="reports",
    )

    __table_args__ = (
        # Prevent the same stored report from being ingested
        # more than once for the same company.
        db.UniqueConstraint(
            "company_id",
            "storage_path",
            name="uq_reports_company_storage_path",
        ),

        # Helps the common company/date/serial-number queries.
        db.Index(
            "ix_reports_company_date_serial",
            "company_id",
            "report_date",
            "serial_number",
        ),
    )



class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    # Unique ID for each audit log entry.
    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    # User who performed the action.
    # SET NULL keeps the log even if the user is deleted later.
    user_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    # Company associated with the action.
    # Useful for filtering logs company-wise.
    company_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "companies.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    # Type of action performed.
    # Example: LOGIN_SUCCESS, USER_CREATED, REPORT_DOWNLOADED.
    action = db.Column(
        db.String(100),
        nullable=False,
        index=True,
    )

    # Type of object affected by the action.
    # Example: USER, COMPANY, REPORT.
    target_type = db.Column(
        db.String(50),
        nullable=True,
    )

    # ID of the affected object.
    # Example: user ID or report ID.
    target_id = db.Column(
        db.Integer,
        nullable=True,
    )

    # IP address from which the action was performed.
    ip_address = db.Column(
        db.String(45),
        nullable=True,
    )

    # Extra structured information about the action.
    # Example: email, role, filename, serial number, etc.
    details = db.Column(
        db.JSON,
        nullable=True,
    )

    # Time at which the action occurred.
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )