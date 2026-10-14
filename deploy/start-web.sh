#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${DATABASE_URL:?Enter the PostgreSQL connection URL in hosting environment settings}"
: "${SECRET_KEY:?Set a generated JWT signing key in hosting environment settings}"
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1 --proxy-headers --forwarded-allow-ips='*'
