"""
Application factory for the Test Report Portal.

This file is responsible for creating and configuring
the Flask application.

Main responsibilities:
- Load application configuration
- Create required folders
- Connect Flask extensions such as PostgreSQL and CSRF protection
- Register application blueprints/routes
- Register command-line utilities
- Create database tables if they do not already exist
"""


from pathlib import Path
from flask import Flask

from .config import Config
from .extensions import db, csrf, migrate



def create_app():
    """
    Create and configure the Flask application.

    This function is called whenever the web application,
    ingestion engine, or other application services need
    access to the Flask configuration and database.
    """
    # -----------------------------------------------------
    # CREATE FLASK APPLICATION
    # -----------------------------------------------------

    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(Config)

    # -----------------------------------------------------
    # CREATE REQUIRED FOLDERS
    # -----------------------------------------------------

    # Ensure the watched folder exists.
    #
    # New Excel reports are placed here so that the
    # ingestion engine can detect and process them.

    
    Path(app.config["STORAGE_DIR"]).mkdir(parents=True, exist_ok=True)

    # -----------------------------------------------------
    # INITIALIZE FLASK EXTENSIONS
    # -----------------------------------------------------

    # Connect SQLAlchemy to the Flask application.
    #
    # SQLAlchemy is used to communicate with PostgreSQL.

    db.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db)

    # -----------------------------------------------------
    # IMPORT APPLICATION MODULES
    # -----------------------------------------------------
    #
    # These imports are kept inside create_app()
    # to avoid circular-import problems between Flask,
    # routes, models and extensions.


    from .auth import auth_bp
    from .reports import reports_bp
    from .admin import admin_bp
    from .cli import register_cli

    # -----------------------------------------------------
    # REGISTER BLUEPRINTS
    # -----------------------------------------------------

    # Authentication routes:
    # login, logout, etc.

    app.register_blueprint(auth_bp)
    # Report routes:
    # report search, filtering and Excel download.
    app.register_blueprint(reports_bp)
    # Administrator routes:
    # companies, users and access management.
    app.register_blueprint(admin_bp)

    # -----------------------------------------------------
    # REGISTER COMMAND-LINE COMMANDS
    # -----------------------------------------------------

    # Add custom Flask CLI commands defined in cli.py.

    register_cli(app)

    

    return app
