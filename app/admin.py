"""
Administration routes for the Test Report Portal.

This module handles:
- Super Admin and Company Admin access
- Admin dashboard statistics
- User creation and management
- User activation/deactivation
- Password reset
- Company creation and activation/deactivation
- Role-based restrictions for managing users

Super Admin can manage all companies and users.
Company Admin can manage only Company Users within their own company.
"""




import secrets
import string

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

from .audit import log_action
from .decorators import get_active_user, roles_required
from .extensions import db
from .models import Company, User

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def random_password(length=16):
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))

def can_manage_user(target):
    """
    Decide whether the logged-in administrator can manage
    the selected user.

    Super Admin:
        Can manage all users.

    Company Admin:
        Can manage only Company Users belonging to
        their own company.
    """

    role = session.get("role")

    if role == User.ROLE_SUPER_ADMIN:
        return True

    return (
        role == User.ROLE_COMPANY_ADMIN
        and target.company_id == session.get("company_id")
        and target.role == User.ROLE_COMPANY_USER
    )




@admin_bp.route("/")
@roles_required(User.ROLE_SUPER_ADMIN, User.ROLE_COMPANY_ADMIN)
def dashboard():
    if session["role"] == User.ROLE_SUPER_ADMIN:
        companies = Company.query.count()
        users = User.query.count()
        reports = ReportCount()
    else:
        company = Company.query.get_or_404(session["company_id"])
        companies = 1
        users = User.query.filter_by(company_id=company.id).count()
        reports = ReportCount(company.id)

    return render_template(
        "admin_dashboard.html",
        companies=companies,
        users=users,
        reports=reports,
    )


def ReportCount(company_id=None):
    from .models import Report
    query = Report.query
    if company_id is not None:
        query = query.filter_by(company_id=company_id)
    return query.count()


@admin_bp.route("/users")
@roles_required(User.ROLE_SUPER_ADMIN, User.ROLE_COMPANY_ADMIN)
def users():
    if session["role"] == User.ROLE_SUPER_ADMIN:
        users = User.query.order_by(User.email).all()
        companies = Company.query.order_by(Company.name).all()
    else:
        users = User.query.filter_by(company_id=session["company_id"]).order_by(User.email).all()
        companies = [Company.query.get_or_404(session["company_id"])]

    return render_template("users.html", users=users, companies=companies)


@admin_bp.route("/users/new", methods=["GET", "POST"])
@roles_required(
    User.ROLE_SUPER_ADMIN,
    User.ROLE_COMPANY_ADMIN,
)
def new_user():
    """
    Create a new portal user.

    Super Admin:
        Can create Company Admins and Company Users.

    Company Admin:
        Can create Company Users only within their own company.
    """

    current_admin = get_active_user()

    # Super Admin can choose from all active companies.
    if current_admin.role == User.ROLE_SUPER_ADMIN:
        companies = (
            Company.query
            .filter_by(is_active=True)
            .order_by(Company.name)
            .all()
        )

    # Company Admin only works inside their own company.
    else:
        companies = [
            Company.query.get_or_404(
                current_admin.company_id
            )
        ]

    if request.method == "POST":

        email = (
            request.form
            .get("email", "")
            .strip()
            .lower()
        )

        password = (
            request.form
            .get("password", "")
            .strip()
        )

        requested_role = request.form.get(
            "role",
            User.ROLE_COMPANY_USER,
        )

        company_id_raw = (
            request.form
            .get("company_id", "")
            .strip()
        )

        # Email is required.
        if not email:
            flash(
                "Email is required.",
                "danger",
            )

            return render_template(
                "user_form.html",
                user=None,
                companies=companies,
            )

        # Prevent duplicate accounts.
        if User.query.filter_by(email=email).first():
            flash(
                "A user with this email already exists.",
                "danger",
            )

            return render_template(
                "user_form.html",
                user=None,
                companies=companies,
            )

        # -------------------------------------------------
        # SUPER ADMIN USER CREATION
        # -------------------------------------------------

        if current_admin.role == User.ROLE_SUPER_ADMIN:

            # Super Admin accounts are NOT created
            # through the web interface.
            if requested_role not in {
                User.ROLE_COMPANY_ADMIN,
                User.ROLE_COMPANY_USER,
            }:
                abort(400)

            if not company_id_raw:
                flash(
                    "Company is required.",
                    "danger",
                )

                return render_template(
                    "user_form.html",
                    user=None,
                    companies=companies,
                )

            try:
                company_id = int(company_id_raw)

            except ValueError:
                abort(400)

            company = db.session.get(
                Company,
                company_id,
            )

            if not company or not company.is_active:
                flash(
                    "Please select an active company.",
                    "danger",
                )

                return render_template(
                    "user_form.html",
                    user=None,
                    companies=companies,
                )

            role = requested_role

        # -------------------------------------------------
        # COMPANY ADMIN USER CREATION
        # -------------------------------------------------

        else:

            # Company Admin cannot choose another company
            # or create another Company Admin.
            company_id = current_admin.company_id
            role = User.ROLE_COMPANY_USER

        # Generate a temporary password when none
        # was manually provided.
        password = password or random_password()

        user = User(
            email=email,
            role=role,
            company_id=company_id,
            is_active=True,

            # User must replace the temporary password
            # on their first login.
            must_change_password=True,
        )

        user.set_password(password)

        db.session.add(user)

        # Flush assigns user.id without committing yet.
        db.session.flush()

        log_action(
            "USER_CREATED",
            user=current_admin,
            company_id=user.company_id,
            target_type="USER",
            target_id=user.id,
            details={
                "email": user.email,
                "role": user.role,
            },
        )

        db.session.commit()

        flash(
            f"User created. Temporary password: {password}",
            "success",
        )

        return redirect(
            url_for("admin.users")
        )

    return render_template(
        "user_form.html",
        user=None,
        companies=companies,
    )

@admin_bp.route(
    "/users/<int:user_id>/toggle",
    methods=["POST"],
)
@roles_required(
    User.ROLE_SUPER_ADMIN,
    User.ROLE_COMPANY_ADMIN,
)
def toggle_user(user_id):

    current_admin = get_active_user()

    user = User.query.get_or_404(user_id)

    if not can_manage_user(user):
        abort(403)

    # Prevent an administrator from disabling
    # their own account.
    if user.id == current_admin.id:
        flash(
            "You cannot disable your own account.",
            "warning",
        )

        return redirect(
            url_for("admin.users")
        )

    user.is_active = not user.is_active

    action = (
        "USER_ENABLED"
        if user.is_active
        else "USER_DISABLED"
    )

    log_action(
        action,
        user=current_admin,
        company_id=user.company_id,
        target_type="USER",
        target_id=user.id,
        details={
            "email": user.email,
        },
    )

    db.session.commit()

    flash(
        "User status updated.",
        "success",
    )

    return redirect(
        url_for("admin.users")
    )


@admin_bp.route(
    "/users/<int:user_id>/reset-password",
    methods=["POST"],
)
@roles_required(
    User.ROLE_SUPER_ADMIN,
    User.ROLE_COMPANY_ADMIN,
)
def reset_password(user_id):

    current_admin = get_active_user()

    user = User.query.get_or_404(user_id)

    if not can_manage_user(user):
        abort(403)

    # Generate a new temporary password.
    password = random_password()

    user.set_password(password)

    # Force the user to create their own password
    # after logging in with the temporary password.
    user.must_change_password = True

    log_action(
        "USER_PASSWORD_RESET",
        user=current_admin,
        company_id=user.company_id,
        target_type="USER",
        target_id=user.id,
        details={
            "email": user.email,
        },
    )

    db.session.commit()

    flash(
        f"Temporary password for {user.email}: {password}",
        "success",
    )

    return redirect(
        url_for("admin.users")
    )


@admin_bp.route("/companies")
@roles_required(User.ROLE_SUPER_ADMIN)
def companies():
    companies = Company.query.order_by(Company.name).all()
    return render_template("companies.html", companies=companies)


@admin_bp.route("/companies/new", methods=["GET", "POST"])
@roles_required(User.ROLE_SUPER_ADMIN)
def new_company():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        code = request.form.get("code", "").strip().upper()

        if not name or not code:
            flash("Company name and code are required.", "danger")

        elif Company.query.filter_by(code=code).first():
            flash("Company code already exists.", "danger")

        else:
            # Get the currently logged-in Super Admin.
            current_admin = get_active_user()

            # Create the company object first.
            company = Company(
                name=name,
                code=code,
                is_active=True,
            )

            db.session.add(company)

            # Assign company.id before committing.
            db.session.flush()

            # Record the company creation in the audit log.
            log_action(
                "COMPANY_CREATED",
                user=current_admin,
                company_id=company.id,
                target_type="COMPANY",
                target_id=company.id,
                details={
                    "name": company.name,
                    "code": company.code,
                },
            )

            # Save both the company and audit log together.
            db.session.commit()

            flash("Company created.", "success")

            return redirect(
                url_for("admin.companies")
            )

    return render_template(
        "company_form.html"
    )


@admin_bp.route(
    "/companies/<int:company_id>/toggle",
    methods=["POST"],
)
@roles_required(User.ROLE_SUPER_ADMIN)
def toggle_company(company_id):

    current_admin = get_active_user()

    company = Company.query.get_or_404(
        company_id
    )

    company.is_active = not company.is_active

    action = (
        "COMPANY_ENABLED"
        if company.is_active
        else "COMPANY_DISABLED"
    )

    log_action(
        action,
        user=current_admin,
        company_id=company.id,
        target_type="COMPANY",
        target_id=company.id,
        details={
            "name": company.name,
            "code": company.code,
        },
    )

    db.session.commit()

    flash(
        "Company status updated.",
        "success",
    )

    return redirect(
        url_for("admin.companies")
    )