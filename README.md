# B2B Sales Pipeline - ChaTask

Hệ thống tự động hóa quy trình bán hàng B2B cho sản phẩm **ChaTask** - Giải pháp quản lý công việc, trao đổi và tài liệu cho doanh nghiệp SME Việt Nam.

## 🎯 Tổng quan

Hệ thống tự động hóa toàn bộ quy trình bán hàng B2B từ **khám phá lead** → **làm giàu dữ liệu** → **tiếp cận đa kênh** → **quản lý pipeline** → **chốt deal**.

## ✨ Tính năng chính

### 🔍 Khám phá Lead (Lead Generation)
- **2 quy trình cào dữ liệu**:
  - **Jobs Signal**: Cào tín hiệu tuyển dụng từ VietnamWorks, TopCV, ITviec
  - **Directory Signal**: Cào danh bạ từ YellowPages, VietnamWorks
- **Apollo.io Integration**: Cào contact C-level qua Chrome CDP
- **5 kênh tín hiệu bổ sung**:
  - News Signals (Google News RSS + báo tài chính VN)
  - Hiệp hội thành viên (HANOISME, VINASA, VCCI, VLA, VNREA)
  - Portfolio công ty (BSSC, VSV Capital, ThinkZone, Toong)
  - Certificate Transparency (crt.sh)
  - Whois .vn domains

### 📧 Tiếp cận đa kênh (Multi-channel Outreach)
- **Email**: SMTP với tracking (open, click, reply)
- **Zalo**: Zalo OA API integration
- **LinkedIn**: Connection requests & messages
- **Sequences & Campaigns**: Multi-step automated campaigns

### 🤖 AI Personalization
- Context-aware content generation (OpenAI/Anthropic)
- Industry-specific templates (13 ngành)
- A/B test variants
- Subject line optimization

### 📊 Deal Pipeline (Kanban)
- 10 stages với validation rules
- Drag-and-drop board
- Pipeline metrics & forecasting
- Bottleneck detection
- Team performance tracking

### 🤖 Automated Scraping
- 4 scraper types (YellowPages, VietnamWorks, Apollo, Signals)
- Background job scheduler (Celery + Redis)
- Job monitoring & retry logic

## 🏗️ Kiến trúc hệ thống

```
b2b_sales_web/
├── app/
│   ├── main.py                 # FastAPI entry point
│   ├── config.py               # Pydantic settings
│   ├── database.py             # Async SQLAlchemy
│   ├── core/                   # Security, Celery
│   ├── models/                 # 13 SQLAlchemy models
│   ├── schemas/                # Pydantic schemas
│   ├── api/v1/                 # 7 REST API modules
│   ├── services/               # Business logic
│   ├── scrapers/               # 4 scrapers + scheduler
│   ├── personalization/        # AI content generation
│   └── deal_pipeline/          # Kanban & pipeline logic
├── tests/                      # 335+ tests
├── alembic/                    # Database migrations
├── docker-compose.yml          # 7 services
├── Dockerfile                  # Multi-stage build
├── nginx.conf                  # Reverse proxy
└── README.md
```

## 🚀 Quick Start

### Yêu cầu
- Docker & Docker Compose
- Python 3.11+ (cho local development)

### Chạy với Docker (Khuyến nghị)

```bash
# 1. Clone repository
git clone <repo-url>
cd b2b_sales_web

# 2. Cấu hình môi trường
cp .env.example .env
# Chỉnh .env với credentials thực tế

# 3. Khởi động toàn bộ stack
docker compose up -d

# 4. Kiểm tra trạng thái
docker compose ps
curl http://localhost/health
```

### Truy cập
| Service | URL |
|---------|-----|
| **API Docs (Swagger)** | http://localhost/docs |
| **API ReDoc** | http://localhost/redoc |
| **Health Check** | http://localhost/health |
| **Flower (Celery Monitor)** | http://localhost:5555 |

## ⚙️ Cấu hình môi trường

Xem `.env.example` để biết đầy đủ các biến môi trường. Các biến quan trọng:

```env
# Security
SECRET_KEY=your-super-secret-key-min-32-chars

# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/b2b_sales

# Redis
REDIS_URL=redis://localhost:6379/0

# Email (SMTP)
SMTP_HOST=smtp.office365.com
SMTP_PORT=587
SMTP_USER=your-email@domain.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=your-email@domain.com

# AI / LLM
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Apollo.io
APOLLO_API_KEY=...

# Zalo OA
ZALO_OA_APP_ID=...
ZALO_OA_SECRET_KEY=...
```

## 📡 API Endpoints chính

### Leads
- `GET /api/v1/leads` - Danh sách leads với filter, pagination
- `POST /api/v1/leads` - Tạo lead mới
- `GET /api/v1/leads/{id}` - Chi tiết lead
- `PATCH /api/v1/leads/{id}` - Cập nhật lead
- `POST /api/v1/leads/{id}/enrich` - Làm giàu dữ liệu lead
- `POST /api/v1/leads/{id}/score` - Chấm điểm lead

### Outreach
- `POST /api/v1/outreach/send` - Gửi outreach đơn/batch
- `GET /api/v1/outreach/templates` - Danh sách template
- `POST /api/v1/outreach/templates` - Tạo template mới
- `POST /api/v1/outreach/sequences` - Tạo sequence
- `POST /api/v1/outreach/campaigns` - Tạo campaign
- `GET /api/v1/outreach/stats` - Thống kê outreach

### Deals
- `GET /api/v1/deals` - Danh sách deals
- `GET /api/v1/deals/pipeline` - Kanban view
- `POST /api/v1/deals` - Tạo deal mới
- `PATCH /api/v1/deals/{id}/stage` - Chuyển stage
- `GET /api/v1/deals/stats` - Thống kê pipeline

### Scraping
- `POST /api/v1/scraping/yellowpages` - Cào YellowPages
- `POST /api/v1/scraping/vietnamworks` - Cào VietnamWorks
- `POST /api/v1/scraping/apollo` - Cào Apollo.io
- `POST /api/v1/scraping/signals` - Cào signals (news, associations)

## 🧪 Testing

```bash
# Chạy tất cả tests
pytest -v

# Chạy test cụ thể
pytest tests/test_manual_send.py -v
pytest tests/test_signals.py -v

# Coverage
pytest --cov=app --cov-report=html
```

## 🐳 Deployment

### Development
```bash
docker compose up -d --build
```

### Production Checklist
- [ ] Set strong `SECRET_KEY` (min 32 chars)
- [ ] Configure production PostgreSQL
- [ ] Set up SSL certificates (Let's Encrypt)
- [ ] Configure nginx reverse proxy
- [ ] Set up monitoring (Sentry, Prometheus)
- [ ] Configure backup strategy
- [ ] Set up CI/CD pipeline

### Environment Variables Production
```env
DEBUG=false
SECRET_KEY=super-secret-production-key
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
REDIS_URL=redis://redis:6379/0
```

## 📁 Cấu trúc thư mục quan trọng

```
b2b_sales_web/
├── app/
│   ├── api/v1/           # 7 API routers
│   ├── models/           # 13 SQLAlchemy models
│   ├── schemas/          # Pydantic schemas
│   ├── services/         # 3 core services
│   ├── scrapers/         # 4 scrapers + scheduler
│   ├── personalization/  # AI content generation
│   └── deal_pipeline/    # Kanban & pipeline logic
├── tests/                # 335+ tests
├── alembic/              # Migrations
├── docker-compose.yml    # 7 services
├── Dockerfile
├── nginx.conf
└── .env.example
```

## 🤝 Contributing

1. Fork repository
2. Create feature branch
3. Make changes with tests
4. Submit PR

## 📄 License

MIT License - see LICENSE file for details.

## 📞 Support

- Issues: GitHub Issues
- Email: support@tcom.vn
- Docs: `/docs` endpoint

---

**B2B Sales Pipeline** - Tự động hóa bán hàng B2B cho ChaTask 🚀