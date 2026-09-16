"""
One-time seed script for the initial Admin account.

Run manually, once, against the target database — never called
automatically by the app or by migrations. Safe to re-run: it checks for
an existing username first and refuses to create a duplicate.

Usage:
    python seed_admin.py
"""

import getpass
import os
import sys

import bcrypt

from config import Config
from db import SessionLocal
from models import User


def main():
    username = os.environ.get("SEED_ADMIN_USERNAME")
    password = os.environ.get("SEED_ADMIN_PASSWORD")
    fullname = os.environ.get("SEED_ADMIN_FULLNAME", "System Administrator")

    if not username:
        username = input("Admin username [admin]: ").strip() or "admin"
    if not password:
        password = getpass.getpass("Admin password: ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Passwords did not match. Aborting.")
            sys.exit(1)

    if not password or len(password) < 8:
        print("Refusing to seed an admin with a password shorter than 8 characters.")
        sys.exit(1)

    session = SessionLocal()
    try:
        existing = session.query(User).filter(User.username == username).first()
        if existing:
            print(f"A user named '{username}' already exists (role: {existing.role}). "
                  f"Not creating a duplicate. Use the Users panel to reset a password instead.")
            sys.exit(1)

        password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        admin = User(
            username=username,
            password_hash=password_hash,
            fullname=fullname,
            role="Super Admin",
            is_active=True,
        )
        session.add(admin)
        session.commit()
        print(f"Admin account '{username}' created successfully.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
