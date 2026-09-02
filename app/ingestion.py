import argparse
import re
import shutil
import time

from datetime import datetime
from pathlib import Path

from flask import current_app

from . import create_app
from .extensions import db
from .models import Recipe, Report


# ------------------------------------------------------------------
# Expected filename format:
#
# I-QUBE-MLX90421_13-06-2026_22.37.26_13.xlsx
#
# Result:
# filename_recipe_name = I-QUBE-MLX90421
# report_date         = 13-06-2026
# report_time         = 22.37.26
# serial_number       = 13
#
# IMPORTANT:
# The recipe/company ownership is NOT determined from the filename.
# Ownership comes from the physical recipe folder and the Recipe table.
#
# The serial number remains a string so values such as
# 03 and 05 retain their leading zero.
# ------------------------------------------------------------------

FILENAME_RE = re.compile(
    r"^(?P<recipe>.+?)"
    r"_(?P<date>\d{2}-\d{2}-\d{4})"
    r"_(?P<time>\d{2}\.\d{2}\.\d{2})"
    r"_(?P<serial>[^_]+)$"
)


def extract_metadata(path: Path):
    """
    Extract report metadata from the original filename.

    Example:

        I-QUBE-MLX90421_13-06-2026_22.37.26_13.xlsx

    produces:

        filename_recipe_name -> I-QUBE-MLX90421
        report_date          -> 2026-06-13
        report_time          -> 22:37:26
        serial_number        -> 13

    The filename recipe name is kept only for diagnostics.

    The actual recipe assigned to the Report comes from the Recipe
    database record associated with the source recipe folder.
    """

    match = FILENAME_RE.match(path.stem)

    if not match:
        raise ValueError(
            f"Filename does not match expected format: {path.name}"
        )

    filename_recipe_name = match.group("recipe").strip()

    report_datetime = datetime.strptime(
        f"{match.group('date')} {match.group('time')}",
        "%d-%m-%Y %H.%M.%S",
    )

    serial_number = match.group("serial").strip()

    if not serial_number:
        raise ValueError(
            f"Serial number is missing from filename: {path.name}"
        )

    return {
        "filename_recipe_name": filename_recipe_name,
        "report_date": report_datetime.date(),
        "report_time": report_datetime.time(),
        "serial_number": serial_number,
        "original_filename": path.name,
    }


def stable(path: Path):
    """
    Check that the source Excel file has finished writing before
    the portal attempts to copy and ingest it.

    Both size and modification timestamp are checked.
    """

    wait = current_app.config["FILE_STABILITY_SECONDS"]

    if not path.exists():
        return False

    try:
        before = path.stat()
    except FileNotFoundError:
        return False

    if wait:
        time.sleep(wait)

    if not path.exists():
        return False

    try:
        after = path.stat()
    except FileNotFoundError:
        return False

    return (
        before.st_size == after.st_size
        and before.st_mtime_ns == after.st_mtime_ns
    )


def source_relative_path(path: Path, source_root: Path):
    """
    Return the path relative to SOURCE_REPORT_ROOT.

    Example source:

        SINGLE DUT REPORT/
            I-QUBE-MLX90421/
                PASS/
                    13-06-2026/
                        report.xlsx

    returns:

        I-QUBE-MLX90421/PASS/13-06-2026/report.xlsx
    """

    try:
        relative = path.relative_to(source_root)
    except ValueError as exc:
        raise RuntimeError(
            f"File is outside SOURCE_REPORT_ROOT: {path}"
        ) from exc

    if len(relative.parts) < 2:
        raise RuntimeError(
            f"Report must be inside a recipe folder: {path}"
        )

    return relative


def recipe_for_source_file(
    path: Path,
    source_root: Path,
):
    """
    Determine the Recipe using the first folder underneath
    SOURCE_REPORT_ROOT.

    Example:

        I-QUBE-MLX90421/PASS/13-06-2026/report.xlsx

    recipe folder:

        I-QUBE-MLX90421

    This folder is matched against Recipe.folder_name.

    No company is guessed from the folder name.
    """

    relative = source_relative_path(
        path,
        source_root,
    )

    recipe_folder = relative.parts[0]

    recipes = (
        Recipe.query
        .filter_by(
            folder_name=recipe_folder,
            is_active=True,
        )
        .all()
    )

    if not recipes:
        return None, recipe_folder, relative

    if len(recipes) > 1:
        raise RuntimeError(
            "More than one active Recipe uses folder_name "
            f"'{recipe_folder}'. Recipe folder mappings must "
            "be unambiguous."
        )

    recipe = recipes[0]

    if recipe.company is None:
        raise RuntimeError(
            f"Recipe '{recipe_folder}' has no company."
        )

    if not recipe.company.is_active:
        raise RuntimeError(
            f"Company '{recipe.company.code}' is inactive."
        )

    return recipe, recipe_folder, relative


def destination_for(
    source_relative: Path,
    recipe: Recipe,
    storage_dir: Path,
):
    """
    Build the portal-controlled storage location.

    Source:

        I-QUBE-MLX90421/
            PASS/
                13-06-2026/
                    report.xlsx

    Destination:

        report_storage/
            TVS/
                I-QUBE-MLX90421/
                    PASS/
                        13-06-2026/
                            report.xlsx
    """

    remaining_parts = source_relative.parts[1:]

    destination = (
        storage_dir
        / recipe.company.code.upper()
        / recipe.folder_name
        / Path(*remaining_parts)
    )

    return destination


def copy_report(
    source: Path,
    destination: Path,
):
    """
    Copy the report from the client/LabVIEW source folder into
    portal-controlled report storage.

    Existing identical files are not unnecessarily copied again.
    """

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if destination.exists():
        try:
            source_stat = source.stat()
            destination_stat = destination.stat()

            same_size = (
                source_stat.st_size
                == destination_stat.st_size
            )

            same_modified_time = (
                source_stat.st_mtime_ns
                == destination_stat.st_mtime_ns
            )

            if same_size and same_modified_time:
                return "UNCHANGED"

        except FileNotFoundError:
            pass

    shutil.copy2(
        source,
        destination,
    )

    return "COPIED"


def ingest_source_file(path: Path):
    """
    Process one report from SOURCE_REPORT_ROOT.

    Flow:

        source report
            ->
        identify recipe folder
            ->
        find Recipe in PostgreSQL
            ->
        determine company from Recipe.company_id
            ->
        copy into STORAGE_DIR
            ->
        create/update Report metadata
    """

    source_root = Path(
        current_app.config["SOURCE_REPORT_ROOT"]
    )

    storage_dir = Path(
        current_app.config["STORAGE_DIR"]
    )

    metadata = extract_metadata(path)

    (
        recipe,
        recipe_folder,
        relative_source,
    ) = recipe_for_source_file(
        path,
        source_root,
    )

    # Unknown recipe folders are skipped safely.
    #
    # This prevents an unconfigured folder from accidentally
    # being assigned to TVS, Mahindra, or another company.
    if recipe is None:
        print(
            "SKIPPED | "
            f"unconfigured_recipe_folder={recipe_folder} | "
            f"file={path.name}"
        )
        return

    company = recipe.company

    # ---------------------------------------------------------
    # Determine portal storage destination
    # ---------------------------------------------------------

    destination = destination_for(
        relative_source,
        recipe,
        storage_dir,
    )

    copy_status = copy_report(
        path,
        destination,
    )

    # ---------------------------------------------------------
    # Store path relative to STORAGE_DIR
    #
    # Example:
    #
    # TVS/I-QUBE-MLX90421/PASS/13-06-2026/report.xlsx
    # ---------------------------------------------------------

    relative_storage = (
        destination
        .relative_to(storage_dir)
        .as_posix()
    )

    # ---------------------------------------------------------
    # Check whether the Report row already exists
    # ---------------------------------------------------------

    report = Report.query.filter_by(
        company_id=company.id,
        storage_path=relative_storage,
    ).first()

    if report:
        report.recipe_id = recipe.id

        # Recipe ownership comes from the Recipe table,
        # not from the filename.
        report.recipe_name = recipe.name

        report.report_date = metadata[
            "report_date"
        ]

        report.report_time = metadata[
            "report_time"
        ]

        report.serial_number = metadata[
            "serial_number"
        ]

        report.original_filename = metadata[
            "original_filename"
        ]

        status = "UPDATED"

    else:
        report = Report(
            company_id=company.id,
            recipe_id=recipe.id,
            recipe_name=recipe.name,
            report_date=metadata[
                "report_date"
            ],
            report_time=metadata[
                "report_time"
            ],
            serial_number=metadata[
                "serial_number"
            ],
            original_filename=metadata[
                "original_filename"
            ],
            storage_path=relative_storage,
        )

        db.session.add(report)

        status = "INGESTED"

    # ---------------------------------------------------------
    # Save metadata to PostgreSQL
    # ---------------------------------------------------------

    db.session.commit()

    print(
        f"{status} | "
        f"copy={copy_status} | "
        f"company={company.code} | "
        f"recipe={recipe.name} | "
        f"folder={recipe.folder_name} | "
        f"filename_recipe="
        f"{metadata['filename_recipe_name']} | "
        f"date={metadata['report_date']} | "
        f"time={metadata['report_time']} | "
        f"serial={metadata['serial_number']} | "
        f"file={path.name}"
    )


def is_candidate_report(path: Path):
    """
    Return True only for supported report files.

    Temporary Excel lock files such as ~$report.xlsx
    are ignored.
    """

    if not path.is_file():
        return False

    if path.name.startswith("~$"):
        return False

    extensions = current_app.config[
        "ALLOWED_REPORT_EXTENSIONS"
    ]

    if path.suffix.lower() not in extensions:
        return False

    return True


def scan_once():
    """
    Scan SOURCE_REPORT_ROOT once.

    New/stable reports are copied into STORAGE_DIR and
    registered in PostgreSQL.
    """

    source_root = Path(
        current_app.config["SOURCE_REPORT_ROOT"]
    )

    storage_dir = Path(
        current_app.config["STORAGE_DIR"]
    )

    if not source_root.exists():
        raise RuntimeError(
            "SOURCE_REPORT_ROOT does not exist: "
            f"{source_root}"
        )

    if not source_root.is_dir():
        raise RuntimeError(
            "SOURCE_REPORT_ROOT is not a directory: "
            f"{source_root}"
        )

    storage_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("=" * 72)
    print("TEST REPORT INGESTION - SINGLE SCAN")
    print(f"Source : {source_root}")
    print(f"Storage: {storage_dir}")
    print("=" * 72)

    for path in source_root.rglob("*"):

        if not is_candidate_report(path):
            continue

        try:
            if stable(path):
                ingest_source_file(path)

        except Exception as exc:
            print(
                f"ERROR | {path} | {exc}"
            )

            # Ensure one bad report does not leave the
            # SQLAlchemy session unusable.
            db.session.rollback()


def watch():
    """
    Continuously monitor SOURCE_REPORT_ROOT for new or
    changed Excel reports.

    The source directory remains untouched.

    Stable reports are copied into STORAGE_DIR before being
    registered in PostgreSQL.
    """

    source_root = Path(
        current_app.config["SOURCE_REPORT_ROOT"]
    )

    storage_dir = Path(
        current_app.config["STORAGE_DIR"]
    )

    if not source_root.exists():
        raise RuntimeError(
            "SOURCE_REPORT_ROOT does not exist: "
            f"{source_root}"
        )

    if not source_root.is_dir():
        raise RuntimeError(
            "SOURCE_REPORT_ROOT is not a directory: "
            f"{source_root}"
        )

    storage_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    seen = set()

    print("=" * 72)
    print("TEST REPORT INGESTION SERVICE")
    print(f"Watching source : {source_root}")
    print(f"Portal storage  : {storage_dir}")
    print(
        "Company mapping : Recipe table "
        "(folder_name -> company)"
    )
    print("=" * 72)

    while True:

        for path in source_root.rglob("*"):

            if not is_candidate_report(path):
                continue

            try:
                file_stat = path.stat()

                key = (
                    str(path.resolve()),
                    file_stat.st_mtime_ns,
                    file_stat.st_size,
                )

            except FileNotFoundError:
                continue

            if key in seen:
                continue

            try:
                if stable(path):
                    ingest_source_file(path)
                    seen.add(key)

            except Exception as exc:
                print(
                    f"ERROR | {path} | {exc}"
                )

                db.session.rollback()

        time.sleep(
            current_app.config[
                "INGESTION_POLL_SECONDS"
            ]
        )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one ingestion scan and exit.",
    )

    args = parser.parse_args()

    app = create_app()

    with app.app_context():

        if args.once:
            scan_once()

        else:
            watch()


if __name__ == "__main__":
    main()