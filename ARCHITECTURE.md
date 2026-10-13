# B2B Sales Pipeline Web Application

## Project Structure
```
b2b_sales_web/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI entry point
│   ├── config.py               # Settings
│   ├── database.py             # DB connection
│   ├── models/                 # SQLAlchemy models
│   │   ├── __init__.py
│   │   ├── lead.py
│   │   ├── outreach.py
│   │   ├── deal.py
│   │   ├── user.py
│   │   └── audit.py
│   ├── schemas/                # Pydantic schemas
│   │   ├── __init__.py
│   │   ├── lead.py
│   │   ├── outreach.py
│   │   ├── deal.py
│   │   └── user.py
│   ├── api/                    # API routes
│   │   ├── __init__.py
│   │   ├── deps.py
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── leads.py
│   │   │   ├── outreach.py
│   │   │   ├── deals.py
│   │   │   ├── scraping.py
│   │   │   └── analytics.py
│   ├── services/               # Business logic
│   │   ├── __init__.py
│   │   ├── lead_service.py
│   │   ├── outreach_service.py
│   │   ├── deal_service.py
│   │   └── analytics_service.py
│   ├── scrapers/               # Data scraping
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── yellowpages.py
│   │   ├── vietnamworks.py
│   │   ├── apollo.py
│   │   ├── signals.py          # News, associations, crt.sh
│   │   └── scheduler.py
│   ├── outreach/               # Multi-channel outreach
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── email.py
│   │   ├── zalo.py
│   │   ├── linkedin.py
│   │   ├── templates.py
│   │   └── scheduler.py
│   ├── personalization/        # AI-driven personalization
│   │   ├── __init__.py
│   │   ├── engine.py
│   │   ├── prompts.py
│   │   └── context_builder.py
│   └── deal_pipeline/          # Deal management
│       ├── __init__.py
│       ├── stages.py
│       ├── kanban.py
│       └── activities.py
├── tests/
├── scripts/
├── alembic/
├── requirements.txt
├── docker-compose.yml
├── Dockerfile
└── .env.example
```

## Core Components

### 1. Configuration & Database
### 2. Data Models (SQLAlchemy)
### 3. API Routes
### 4. Scraping Engine (2 processes)
### 5. Outreach Engine (Email/Zalo/LinkedIn)
### 6. Personalization Engine
### 7. Deal Pipeline (Kanban)
### 8. Background Workers (Celery)
### 9. Frontend (React + Tailwind)
### 10. Deployment (Docker)

Let me start building each component.