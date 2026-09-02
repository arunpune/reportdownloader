from app import create_app
from app.extensions import db
from app.models import Company, User

app = create_app()

with app.app_context():
    company = Company.query.filter_by(code=app.config["DEMO_COMPANY_CODE"]).first()
    if not company:
        company = Company(
            name=app.config["DEMO_COMPANY_NAME"],
            code=app.config["DEMO_COMPANY_CODE"],
            is_active=True,
        )
        db.session.add(company)
        db.session.flush()

    super_admin = User.query.filter_by(
        email=app.config["DEMO_SUPER_ADMIN_EMAIL"].lower()
    ).first()
    if not super_admin:
        super_admin = User(
            company_id=None,
            email=app.config["DEMO_SUPER_ADMIN_EMAIL"].lower(),
            role=User.ROLE_SUPER_ADMIN,
            is_active=True,
        )
        super_admin.set_password(app.config["DEMO_SUPER_ADMIN_PASSWORD"])
        db.session.add(super_admin)

    admin = User.query.filter_by(email=app.config["DEMO_ADMIN_EMAIL"].lower()).first()
    if not admin:
        admin = User(
            company_id=company.id,
            email=app.config["DEMO_ADMIN_EMAIL"].lower(),
            role=User.ROLE_COMPANY_ADMIN,
            is_active=True,
        )
        admin.set_password(app.config["DEMO_ADMIN_PASSWORD"])
        db.session.add(admin)

    user = User.query.filter_by(email=app.config["DEMO_USER_EMAIL"].lower()).first()
    if not user:
        user = User(
            company_id=company.id,
            email=app.config["DEMO_USER_EMAIL"].lower(),
            role=User.ROLE_COMPANY_USER,
            is_active=True,
        )
        user.set_password(app.config["DEMO_USER_PASSWORD"])
        db.session.add(user)

    db.session.commit()

    print("Demo database ready.")
    print(f"Super Admin: {app.config['DEMO_SUPER_ADMIN_EMAIL']}")
    print(f"Company Admin: {app.config['DEMO_ADMIN_EMAIL']}")
    print(f"Company User: {app.config['DEMO_USER_EMAIL']}")
