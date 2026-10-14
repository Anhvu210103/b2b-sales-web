# Local development

This checkout contains a FastAPI backend and a built-in Vietnamese sales web UI.
Use Python 3.11, PostgreSQL 15 and Redis 7. The UI is served by the same API process
at `/`, with assets at `/assets`; there is no additional frontend build or service.

In the prepared cloud environment:

```bash
cd /workspace/b2b-sales-web
source .venv/bin/activate
bash /workspace/b2b-runtime/services.sh
set -a
source /workspace/b2b-runtime/dev.env
set +a
```

The local settings file contains a generated development JWT key. PostgreSQL
uses trust authentication with its port bound to loopback for this isolated
development workflow. Use authenticated database connections in deployments.
These Docker containers are development services; do not assume their database
contents survive restoration into a new machine.

Start these commands in separate terminals:

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
celery -A app.core.celery_app worker --loglevel=info --concurrency=2
```

The API initializes missing database tables at startup. Scraping job state is
shared through Redis and scraping tasks execute in Celery workers. Beat can run
with `celery -A app.core.celery_app beat --loglevel=info`; there are no recurring
scraping schedules configured by default.

Create your first administrator with a password entered securely at the prompt:

```bash
python -m app.cli create-admin --email your-email@example.com --name Administrator
```

Existing accounts are never overwritten by this command. Authenticate through
`POST /api/v1/auth/login` with OAuth2 form fields `username` (email) and `password`.

Internally verify `/health`, `/openapi.json` and authenticated API requests.
Swagger documentation is served at `/docs`.

The web UI includes login, dashboard, searchable and paginated customer lists,
customer details/editing, deal creation, a 10-stage Kanban board with drag and
drop, accessible stage selection, and a deal activity timeline with notes.
JWT sessions are kept in the current browser tab and cleared on logout or expiry.
Create an administrator with the command above, then log in through the web UI.
Nginx forwards both the UI and the API to FastAPI.

Run regression tests from the repository root:

```bash
python -m pytest -q
```

Database tests create and remove disposable schemas and do not reset application
tables. The configured PostgreSQL user needs permission to create schemas.
Set `TEST_DATABASE_URL` to use a separate test database. Scraping tests mock
external sites and remove only their own Redis job records.
The browser regression also needs Chromium (or the Playwright browser installed)
and checks the sales workflow, session restoration, logout and mobile layout.

For a fresh Python environment, install `requirements.txt` into a virtual
environment. The cloud machine already supplies `/usr/bin/chromium`; set
`PLAYWRIGHT_EXECUTABLE_PATH=/usr/bin/chromium` to use it. On other machines use
`python -m playwright install chromium` and install the supported browser system
dependencies. The default downloads were denied by cloud network policy, so the
prepared environment uses its existing system Chromium, validated with a local
DOM read.

External SMTP, AI, Zalo, LinkedIn and Apollo operations need their real settings
and destination access. They are not exercised by the local regression tests;
no messages are sent or external sites scraped during setup.
