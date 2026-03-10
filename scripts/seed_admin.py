#!/usr/bin/env python3
"""Seed the first owner account for Solar Admin AI.

Usage:
    python scripts/seed_admin.py

Creates an owner-role user in the users table. Run once after deploying.
Passwords are hashed with bcrypt to match the login endpoint in api/auth.py.
"""
import sys
import os
import getpass

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bcrypt
from memory.database import init_db, get_conn, fetch_one


def seed_admin():
    """Interactively create the first owner account."""
    init_db()

    print("\n=== Solar Admin AI — Create Owner Account ===\n")

    name     = input("Full name: ").strip()
    email    = input("Email:     ").strip().lower()
    password = getpass.getpass("Password (8+ chars): ")
    confirm  = getpass.getpass("Confirm password:    ")

    if not name or not email or not password:
        print("ERROR: All fields required.")
        sys.exit(1)

    if password != confirm:
        print("ERROR: Passwords don't match.")
        sys.exit(1)

    if len(password) < 8:
        print("ERROR: Password must be at least 8 characters.")
        sys.exit(1)

    existing = fetch_one("SELECT id FROM users WHERE email = ?", (email,))
    if existing:
        print(f"ERROR: User {email} already exists.")
        sys.exit(1)

    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    with get_conn() as conn:
        conn.execute(
            "INSERT INTO users (name, email, password_hash, role, active, created_at) "
            "VALUES (?, ?, ?, 'owner', 1, datetime('now'))",
            (name, email, pw_hash),
        )

    print(f"\n✓ Owner account created: {email}")
    print("  You can now log in at http://localhost:5173\n")


if __name__ == "__main__":
    seed_admin()
