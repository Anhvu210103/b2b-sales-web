import asyncio
import ssl
from pydantic import SecretStr
from sqlalchemy import delete, select
from app.core.database_url import connection_options
from app.config import settings
from app.core.security import verify_password
from app.models.user import User, UserRole
from app import database


def test_hosted_postgres_url_requires_verified_tls():
    url, args = connection_options(
        "postgresql://user:password@db.example.com/crm?sslmode=require&channel_binding=require"
    )
    assert url.drivername == "postgresql+asyncpg"
    assert "sslmode" not in url.query
    assert "channel_binding" not in url.query
    assert args["ssl"].verify_mode == ssl.CERT_REQUIRED
    assert args["ssl"].check_hostname
    assert connection_options("postgresql+asyncpg://localhost/crm")[1] == {}


def test_bootstrap_only_creates_first_admin(client, monkeypatch):
    from app.bootstrap import bootstrap_admin
    monkeypatch.setattr(settings, "B2B_BOOTSTRAP_EMAIL", "owner@example.com")
    monkeypatch.setattr(settings, "B2B_BOOTSTRAP_PASSWORD", SecretStr("Personal-Password-2026"))

    async def check():
        async with database.async_session_factory() as session:
            await session.execute(delete(User))
            await session.commit()
        await bootstrap_admin()
        monkeypatch.setattr(settings, "B2B_BOOTSTRAP_PASSWORD", SecretStr("Changed-Password-2026"))
        await bootstrap_admin()
        async with database.async_session_factory() as session:
            users = (await session.scalars(select(User))).all()
            assert len(users) == 1
            assert users[0].role == UserRole.ADMIN
            assert verify_password("Personal-Password-2026", users[0].hashed_password)
            assert not verify_password("Changed-Password-2026", users[0].hashed_password)
    asyncio.run(check())


def test_login_attempts_are_limited(client):
    results = [client.post("/api/v1/auth/login", data={
        "username": "admin@example.com", "password": "wrong",
    }).status_code for _ in range(6)]
    assert results[:5] == [401] * 5
    assert results[5] == 429
