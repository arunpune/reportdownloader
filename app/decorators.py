"""
Authorization helpers for the Test Report Portal.

Every protected request checks PostgreSQL again so that:
- the logged-in user still exists,
- the user account is active,
- the user's company is active,
- the latest role and company are used.

This prevents an old browser session from keeping access after
a user or company has been disabled.
"""

from functools import wraps

from flask import abort, redirect, request, session, url_for

from .extensions import db
from .models import User


def request_path():
    """
    Return the page the user originally tried to open.

    After login, Flask can redirect the user back to this page.
    """
    return request.full_path


def get_active_user():
    """
    Load the currently logged-in user directly from PostgreSQL.

    We do not rely only on role/company information saved in
    the session because an administrator may have changed those
    values after the user originally logged in.
    """

    user_id = session.get("user_id")

    # No user_id means the visitor is not logged in.
    if not user_id:
        return None

    # Always fetch the latest user record from PostgreSQL.
    user = db.session.get(User, user_id)

    # The user may have been deleted or disabled.
    if not user or not user.is_active:
        session.clear()
        return None

    # Super Admin does not belong to one company.
    # Company Admin and Company User must belong to
    # an active company.
    if user.role != User.ROLE_SUPER_ADMIN:

        if not user.company or not user.company.is_active:
            session.clear()
            return None

    # Refresh session values using the latest database data.
    session["role"] = user.role
    session["company_id"] = user.company_id
    session["user_email"] = user.email

    return user


def login_required(view):
    """
    Allow access only to an active authenticated user.
    """

    @wraps(view)
    def wrapped(*args, **kwargs):

        user = get_active_user()

        if not user:
            return redirect(
                url_for(
                    "auth.login",
                    next=request_path(),
                )
            )

        # A temporary-password user may only change
        # their password or log out.
        if (
            user.must_change_password
            and request.endpoint not in {
                "auth.change_password",
                "auth.logout",
            }
        ):
            return redirect(
                url_for("auth.change_password")
            )

        return view(*args, **kwargs)

    return wrapped


def roles_required(*roles):
    """
    Allow access only when the user's CURRENT PostgreSQL role
    is one of the roles permitted for the requested page.
    """

    def decorator(view):

        @wraps(view)
        def wrapped(*args, **kwargs):

            user = get_active_user()

            if not user:
                return redirect(
                    url_for("auth.login")
                )

            if (
                user.must_change_password
                and request.endpoint not in {
                    "auth.change_password",
                    "auth.logout",
                }
            ):
                return redirect(
                    url_for("auth.change_password")
                )

            if user.role not in roles:
                abort(403)

            return view(*args, **kwargs)

        return wrapped

    return decorator