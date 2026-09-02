from datetime import datetime, date, timedelta
from pathlib import Path

from flask import (
    Blueprint,
    abort,
    current_app,
    render_template,
    request,
    send_file,
    session,
    redirect,
    url_for,
)

from .decorators import login_required
from .models import Recipe, Report


reports_bp = Blueprint("reports", __name__)


# =========================================================
# ACCESS CONTROL - REPORTS
# =========================================================

def accessible_query():
    """
    Return only reports that the logged-in user is allowed
    to access.

    SUPER_ADMIN:
        Can see reports from all companies.

    COMPANY_ADMIN / COMPANY_USER:
        Can see only reports belonging to their company.
    """

    query = Report.query

    if session.get("role") != "SUPER_ADMIN":
        query = query.filter(
            Report.company_id == session.get("company_id")
        )

    return query


# =========================================================
# ACCESS CONTROL - RECIPES
# =========================================================

def accessible_recipes_query():
    """
    Return only active recipes that the logged-in user
    is allowed to access.

    SUPER_ADMIN:
        Can see recipes from all companies.

    COMPANY_ADMIN / COMPANY_USER:
        Can see only recipes belonging to their company.
    """

    query = Recipe.query.filter(
        Recipe.is_active.is_(True)
    )

    if session.get("role") != "SUPER_ADMIN":
        query = query.filter(
            Recipe.company_id == session.get("company_id")
        )

    return query


# =========================================================
# HOME
# =========================================================

@reports_bp.route("/")
def home():

    if session.get("user_id"):
        return redirect(
            url_for("reports.list_reports")
        )

    return redirect(
        url_for("auth.login")
    )


# =========================================================
# REPORT LIST / SEARCH
# =========================================================

@reports_bp.route("/reports")
@login_required
def list_reports():

    # -----------------------------------------------------
    # Read filters from URL
    # -----------------------------------------------------

    recipe_raw = request.args.get(
        "recipe",
        ""
    ).strip()

    report_date_raw = request.args.get(
        "date",
        ""
    ).strip()

    serial = request.args.get(
        "serial",
        ""
    ).strip()


    # =====================================================
    # RECIPE VALIDATION
    # =====================================================
    #
    # The browser sends a recipe ID.
    #
    # Example:
    #
    #     /reports?recipe=2
    #
    # We NEVER trust that ID directly.
    #
    # It must first exist inside accessible_recipes_query().
    #
    # Therefore a TVS user cannot manually enter the ID
    # of a Mahindra recipe and gain access to it.
    # =====================================================

    selected_recipe = None
    selected_recipe_id = None

    if recipe_raw:

        try:
            selected_recipe_id = int(
                recipe_raw
            )

        except (ValueError, TypeError):
            abort(
                400,
                "Invalid recipe."
            )

        selected_recipe = (
            accessible_recipes_query()
            .filter(
                Recipe.id == selected_recipe_id
            )
            .first()
        )

        if selected_recipe is None:
            abort(
                403,
                "You do not have access to this recipe."
            )


    # =====================================================
    # DETERMINE REPORT DATE
    # =====================================================
    #
    # By default, show reports for yesterday.
    #
    # Example:
    #
    # Today:       31 August 2026
    # Report date: 30 August 2026
    # =====================================================

    default_report_date = (
        date.today()
        - timedelta(days=1)
    )

    report_date = default_report_date

    if report_date_raw:

        try:

            report_date = datetime.strptime(
                report_date_raw,
                "%Y-%m-%d"
            ).date()

        except ValueError:

            report_date = default_report_date


    # =====================================================
    # PAGINATION
    # =====================================================

    try:

        page = max(
            1,
            int(
                request.args.get(
                    "page",
                    1
                )
            )
        )

    except (ValueError, TypeError):

        page = 1


    # =====================================================
    # BASE REPORT QUERY
    # =====================================================

    query = accessible_query()


    # =====================================================
    # RECIPE FILTER
    # =====================================================
    #
    # We now filter using recipe_id instead of doing text
    # matching against recipe_name.
    # =====================================================

    if selected_recipe is not None:

        query = query.filter(
            Report.recipe_id
            == selected_recipe.id
        )


    # =====================================================
    # DATE FILTER
    # =====================================================

    query = query.filter(
        Report.report_date == report_date
    )


    # =====================================================
    # SERIAL NUMBER FILTER
    # =====================================================

    if serial:

        query = query.filter(
            Report.serial_number == serial
        )


    # =====================================================
    # COUNT
    # =====================================================

    total_reports = query.count()

    per_page = current_app.config[
        "REPORTS_PER_PAGE"
    ]

    total_pages = max(
        1,
        (
            total_reports
            + per_page
            - 1
        ) // per_page
    )

    page = min(
        page,
        total_pages
    )


    # =====================================================
    # FETCH REPORTS
    # =====================================================

    reports = (
        query
        .order_by(
            Report.report_date.desc(),
            Report.report_time.desc().nullslast(),
            Report.id.desc(),
        )
        .offset(
            (page - 1) * per_page
        )
        .limit(per_page)
        .all()
    )


    # =====================================================
    # RECIPE DROPDOWN
    # =====================================================
    #
    # Recipe options now come directly from the recipes
    # table rather than from distinct Report.recipe_name.
    #
    # Therefore recipes can appear in the dropdown even if
    # they currently contain zero reports.
    # =====================================================

    recipes = (
        accessible_recipes_query()
        .order_by(
            Recipe.name.asc()
        )
        .all()
    )


    # =====================================================
    # REPORT HEADING
    # =====================================================

    serial_display = (
        serial
        if serial
        else "All"
    )

    reports_heading = (
        "Reports for the date: "
        f"{report_date.strftime('%d %B %Y')} "
        "for Serial Number: "
        f"{serial_display}"
    )


    # =====================================================
    # PROCESSING MESSAGE
    # =====================================================

    show_processing_message = (
        report_date
        == default_report_date
    )


    # =====================================================
    # RENDER PAGE
    # =====================================================

    return render_template(
        "reports.html",

        reports=reports,

        recipes=recipes,

        filters={
            "recipe": (
                str(selected_recipe_id)
                if selected_recipe_id is not None
                else ""
            ),
            "date": (
                report_date_raw
                if report_date_raw
                else default_report_date.isoformat()
            ),
            "serial": serial,
        },

        selected_recipe=selected_recipe,

        reports_heading=reports_heading,

        report_date=report_date,

        show_processing_message=show_processing_message,

        page=page,

        total_pages=total_pages,

        total_reports=total_reports,

        reports_per_page=per_page,
    )


# =========================================================
# DOWNLOAD REPORT
# =========================================================

@reports_bp.route(
    "/download/<int:report_id>"
)
@login_required
def download(report_id):

    # -----------------------------------------------------
    # ACCESS CONTROL
    # -----------------------------------------------------
    #
    # Use the same accessible report query here.
    #
    # Example:
    #
    # TVS user manually tries:
    #
    #     /download/500
    #
    # If report 500 belongs to Mahindra,
    # accessible_query() will not return it.
    # -----------------------------------------------------

    report = (
        accessible_query()
        .filter(
            Report.id == report_id
        )
        .first_or_404()
    )


    # -----------------------------------------------------
    # STORAGE PATH
    # -----------------------------------------------------

    base = Path(
        current_app.config[
            "STORAGE_DIR"
        ]
    ).resolve()

    path = (
        base
        / report.storage_path
    ).resolve()


    # -----------------------------------------------------
    # PATH SECURITY
    # -----------------------------------------------------

    if (
        base not in path.parents
        or not path.is_file()
    ):

        abort(
            404,
            "Original report file is missing from storage."
        )


    # -----------------------------------------------------
    # DOWNLOAD ORIGINAL EXCEL
    # -----------------------------------------------------

    return send_file(
        path,
        as_attachment=True,
        download_name=report.original_filename,
    )