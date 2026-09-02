"""
Authentication routes for the Test Report Portal.

This module handles:
- User login
- Email and password verification
- Active user validation
- Active company validation
- Flask session creation
- User logout

User roles and company access are loaded from PostgreSQL.
Super Admin is not tied to a company, while Company Admin
and Company User must belong to an active company.
"""



from datetime import datetime, timezone

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from .audit import log_action
from .decorators import get_active_user, login_required
from .extensions import db
from .models import User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("reports.list_reports"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        

        user = User.query.filter_by(email=email).first()

        # Reject invalid credentials or disabled accounts.
        if (
            not user
            or not user.is_active
            or not user.check_password(password)
        ):
            log_action(
                "LOGIN_FAILED",
                user=user if user else None,
                details={
                    "email": email,
                },
            )

            db.session.commit()

            flash(
                "Invalid email or password.",
                "danger",
            )

            return render_template(
                "login.html"
            ), 401


        # Reject users whose company has been disabled.
        # Super Admin does not belong to a company.
        if (
            user.role != User.ROLE_SUPER_ADMIN
            and (
                not user.company
                or not user.company.is_active
            )
        ):
            log_action(
                "LOGIN_FAILED",
                user=user,
                details={
                    "email": email,
                    "reason": "inactive_company",
                },
            )

            db.session.commit()

            flash(
                "Invalid email or password.",
                "danger",
            )

            return render_template(
                "login.html"
            ), 401


        # Store the most recent successful login time.
        user.last_login_at = datetime.now(timezone.utc)

        # Record the successful login.
        log_action(
            "LOGIN_SUCCESS",
            user=user,
        )

        db.session.commit()

        session.clear()
        session.permanent = True
        session["user_id"] = user.id
        session["role"] = user.role
        session["company_id"] = user.company_id
        session["user_email"] = user.email

        # Users created with a temporary password must
        # choose their own password before accessing the portal.
        if user.must_change_password:
            return redirect(
                url_for("auth.change_password")
            )

        next_url = request.args.get("next")
        if next_url and next_url.startswith("/"):
            return redirect(next_url)

        return redirect(url_for("reports.list_reports"))

    return render_template("login.html")


@auth_bp.route(
    "/change-password",
    methods=["GET", "POST"],
)
@login_required
def change_password():
    """
    Allow the logged-in user to replace their current password.

    Newly created users are required to complete this step
    before accessing the rest of the portal.
    """

    user = get_active_user()

    if request.method == "POST":
        current_password = request.form.get(
            "current_password",
            ""
        )

        new_password = request.form.get(
            "new_password",
            ""
        )

        confirm_password = request.form.get(
            "confirm_password",
            ""
        )

        # Verify the user's current password.
        if not user.check_password(current_password):
            flash(
                "Current password is incorrect.",
                "danger",
            )

            return render_template(
                "change_password.html"
            )

        # Require both new-password fields to match.
        if new_password != confirm_password:
            flash(
                "New passwords do not match.",
                "danger",
            )

            return render_template(
                "change_password.html"
            )

        # Keep the minimum password length at 12 characters.
        if len(new_password) < 12:
            flash(
                "Password must be at least 12 characters long.",
                "danger",
            )

            return render_template(
                "change_password.html"
            )

        # Prevent reusing the current password.
        if user.check_password(new_password):
            flash(
                "New password must be different from the current password.",
                "danger",
            )

            return render_template(
                "change_password.html"
            )

        user.set_password(new_password)
        user.must_change_password = False

        log_action(
            "PASSWORD_CHANGED",
            user=user,
        )

        db.session.commit()

        flash(
            "Password changed successfully.",
            "success",
        )

        return redirect(
            url_for("reports.list_reports")
        )

    return render_template(
        "change_password.html"
    )


@auth_bp.route("/logout")
@login_required
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))
