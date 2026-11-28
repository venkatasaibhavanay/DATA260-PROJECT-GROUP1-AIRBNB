"""Create or reset the seeded admin account (admins never sign up through the API).

    cd backend/user-service
    PYTHONPATH=.:../.. ../../.venv/bin/python -m app.seed_admin --email admin@group1.dev --name "Group 1 Admin"

The password is prompted for (not passed on the command line).
"""
import argparse
import getpass
import sys

from sqlalchemy.orm import Session

from app.database.connection import get_mysql_engine
from app.models import Admin
from app.repositories.users import get_admin_by_email
from app.services.security import hash_password, password_problem


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--email", required=True)
    ap.add_argument("--name", default="Group 1 Admin")
    args = ap.parse_args()
    password = getpass.getpass("Admin password: ")
    if (problem := password_problem(password)):
        print(problem, file=sys.stderr)
        return 1
    email = args.email.strip().lower()
    with Session(get_mysql_engine()) as db, db.begin():
        admin = get_admin_by_email(db, email)
        if admin:
            admin.password_hash, admin.name = hash_password(password), args.name
            print(f"Updated admin {email} (id {admin.admin_id}).")
        else:
            db.add(Admin(name=args.name, email=email, password_hash=hash_password(password)))
            print(f"Created admin {email}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
