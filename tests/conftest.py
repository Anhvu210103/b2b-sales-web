"""Integration tests use a disposable PostgreSQL schema, never application data."""

import asyncio
import os
import secrets
from uuid import uuid4

os.environ.setdefault("SECRET_KEY", secrets.token_urlsafe(48))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app import database
from app.config import settings
from app.core.security import get_password_hash
from app.models.user import User, UserRole
from app.main import app


@pytest.fixture
def client(monkeypatch):
    from app.core.rate_limit import limiter
    limiter.reset()
    schema = "test_" + uuid4().hex
    url = os.environ.get("TEST_DATABASE_URL", settings.DATABASE_URL)
    admin = create_async_engine(url, poolclass=NullPool)
    engine = create_async_engine(
        url, poolclass=NullPool, connect_args={"server_settings": {"search_path": schema}}
    )
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def prepare():
        async with admin.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        async with engine.begin() as connection:
            await connection.run_sync(database.Base.metadata.create_all)
        async with sessions() as session:
            session.add(User(
                email="admin@example.com", full_name="Test Admin", role=UserRole.ADMIN,
                hashed_password=get_password_hash("Test-Password-2026"),
            ))
            await session.commit()

    async def cleanup():
        await engine.dispose()
        async with admin.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin.dispose()

    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "async_session_factory", sessions)
    import app.main as main
    monkeypatch.setattr(main, "engine", engine)
    try:
        asyncio.run(prepare())
        with TestClient(app) as test_client:
            yield test_client
    finally:
        asyncio.run(cleanup())


@pytest.fixture
def authenticated(client):
    response = client.post("/api/v1/auth/login", data={
        "username": "admin@example.com", "password": "Test-Password-2026",
    })
    assert response.status_code == 200, response.text
    client.headers["Authorization"] = "Bearer " + response.json()["access_token"]
    return client
