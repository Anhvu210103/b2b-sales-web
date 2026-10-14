"""Local administration commands: python -m app.cli create-admin."""

import argparse
import asyncio
import getpass

from email_validator import validate_email
from sqlalchemy import select

from app.core.security import get_password_hash
from app.database import async_session_factory, engine, init_db
from app.models.user import User, UserRole


async def create_admin(email: str, full_name: str, password: str):
    try:
        await init_db()
        async with async_session_factory() as session:
            existing = await session.scalar(select(User).where(User.email == email))
            if existing:
                raise ValueError("User already exists; no credentials or roles changed")
            session.add(User(
                email=email, full_name=full_name, role=UserRole.ADMIN,
                is_superuser=True, hashed_password=get_password_hash(password),
            ))
            await session.commit()
    finally:
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["create-admin"])
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", default="Administrator")
    args = parser.parse_args()
    email = validate_email(args.email, check_deliverability=False).normalized
    password = getpass.getpass("Admin password: ")
    if len(password) < 8 or len(password.encode()) > 72:
        parser.error("Password must have at least 8 characters and at most 72 UTF-8 bytes")
    if password != getpass.getpass("Confirm password: "):
        parser.error("Passwords do not match")
    try:
        asyncio.run(create_admin(email, args.name, password))
    except ValueError as exc:
        parser.error(str(exc))
    print("Administrator created")


if __name__ == "__main__":
    main()
