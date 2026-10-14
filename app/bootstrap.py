"""Optional first-admin bootstrap for hosting plans without an interactive shell."""

from email_validator import validate_email
from sqlalchemy import select, text

from app.config import settings
from app.core.security import get_password_hash
from app import database
from app.models.user import User, UserRole


async def bootstrap_admin():
    if not settings.B2B_BOOTSTRAP_EMAIL and not settings.B2B_BOOTSTRAP_PASSWORD:
        return
    if not settings.B2B_BOOTSTRAP_EMAIL or not settings.B2B_BOOTSTRAP_PASSWORD:
        raise ValueError("Configure both B2B_BOOTSTRAP_EMAIL and B2B_BOOTSTRAP_PASSWORD")
    async with database.async_session_factory() as session:
        # Serialize competing startups; never reset an existing account's password.
        await session.execute(text("SELECT pg_advisory_xact_lock(194827631)"))
        existing_admin = await session.scalar(select(User.id).where(User.role == UserRole.ADMIN).limit(1))
        if existing_admin is not None:
            return
        email = validate_email(settings.B2B_BOOTSTRAP_EMAIL, check_deliverability=False).normalized
        password = settings.B2B_BOOTSTRAP_PASSWORD.get_secret_value()
        if len(password) < 12 or len(password.encode()) > 72:
            raise ValueError("Bootstrap password needs at least 12 characters and at most 72 UTF-8 bytes")
        if await session.scalar(select(User.id).where(User.email == email)):
            raise ValueError("Bootstrap email belongs to an existing user; no role or password changed")
        session.add(User(
            email=email, full_name="Administrator", role=UserRole.ADMIN,
            is_superuser=True, hashed_password=get_password_hash(password),
        ))
        await session.commit()
