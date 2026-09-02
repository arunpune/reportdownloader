"""
Command-line utilities for the Test Report Portal.

This module provides Flask CLI commands for:
- Creating a Super Admin account
- Creating new companies

These commands are useful for initial setup and administration
without using the web interface.
"""


import click
from flask import current_app

from .extensions import db
from .models import Company, User


def register_cli(app):
    @app.cli.command("create-super-admin")
    @click.option("--email", prompt=True)
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
    def create_super_admin(email, password):
        email = email.strip().lower()
        existing = User.query.filter_by(email=email).first()
        if existing:
            click.echo("A user with that email already exists.")
            return

        user = User(
            email=email,
            role=User.ROLE_SUPER_ADMIN,
            company_id=None,
            is_active=True,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Super Admin created: {email}")

    @app.cli.command("create-company")
    @click.option("--name", prompt=True)
    @click.option("--code", prompt=True)
    def create_company(name, code):
        code = code.strip().upper()
        if Company.query.filter_by(code=code).first():
            click.echo("Company code already exists.")
            return
        db.session.add(Company(name=name.strip(), code=code, is_active=True))
        db.session.commit()
        click.echo(f"Company created: {code}")
