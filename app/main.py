"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from pathlib import Path
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.core.rate_limit import limiter

from app.config import settings
from app.database import engine, init_db
from app.api.v1 import router as api_v1_router
from app.bootstrap import bootstrap_admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    await bootstrap_admin()
    yield
    # Shutdown
    await engine.dispose()



app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="B2B Sales Pipeline API",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# API routes
app.include_router(api_v1_router, prefix="/api/v1")

web_dir = Path(__file__).parent / "web"
app.mount("/assets", StaticFiles(directory=web_dir), name="web-assets")


@app.get("/", include_in_schema=False)
async def web_app():
    return FileResponse(web_dir / "index.html")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": settings.APP_VERSION}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logging.getLogger(__name__).error("Unhandled application error", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "message": "Không thể xử lý yêu cầu. Vui lòng thử lại."},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )
