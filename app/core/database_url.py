"""Adapt provider PostgreSQL URLs to asyncpg without dropping TLS verification."""

import ssl
from sqlalchemy.engine import make_url


def connection_options(raw_url: str):
    url = make_url(raw_url)
    if url.drivername in ("postgres", "postgresql"):
        url = url.set(drivername="postgresql+asyncpg")
    query = dict(url.query)
    connect_args = {}
    mode = query.pop("sslmode", None)
    root_cert = query.pop("sslrootcert", None)
    # libpq-only option: asyncpg authenticates through its own SCRAM implementation.
    query.pop("channel_binding", None)
    if mode in ("require", "verify-ca", "verify-full"):
        connect_args["ssl"] = ssl.create_default_context(cafile=root_cert)
    elif mode == "disable":
        connect_args["ssl"] = False
    elif mode is not None:
        raise ValueError("Unsupported sslmode; use verify-full for hosted PostgreSQL")
    if root_cert and mode not in ("require", "verify-ca", "verify-full"):
        raise ValueError("sslrootcert requires an explicitly verified TLS connection")
    return url.set(query=query), connect_args
