"""
Audit logging helper for the Test Report Portal.

Important security and administrative actions are stored
in PostgreSQL so that administrators can review system activity.
"""

from flask import request

from .extensions import db
from .models import AuditLog


def log_action(
    action,
    user=None,
    company_id=None,
    target_type=None,
    target_id=None,
    details=None,
):
    """
    Add an audit-log entry to the current database transaction.

    The calling route is responsible for committing the transaction.
    """

    # Use the explicitly supplied company when available.
    # Otherwise use the company belonging to the current user.
    resolved_company_id = (
        company_id
        if company_id is not None
        else (user.company_id if user else None)
    )

    log = AuditLog(
        user_id=user.id if user else None,
        company_id=resolved_company_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        ip_address=request.remote_addr,
        details=details,
    )

    db.session.add(log)