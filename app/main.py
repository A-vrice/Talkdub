"""
FastAPI アプリケーション本体
Design原則: 1. シンプルにする、65. 0.1秒以内に反応を返す
"""
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import logging
from pathlib import Path

from config.settings import settings
from app.api import jobs, download

# ログ設定
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(settings.LOGS_DIR / "app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# レート制限（Design原則: 15. エラーを回避する）
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="MultiLang Voice Lab",
    description="多言語音声変換研究プラットフォーム",
    version="0.1.0",
    docs_url="/api/docs" if settings.DEBUG else None,  # 本番では無効化
    redoc_url=None
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# セキュリティヘッダー（Design原則: 13. コンストレイント）
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline';"
    )
    return response

# API ルーター登録
app.include_router(jobs.router, prefix="/api/v1", tags=["jobs"])
app.include_router(download.router, prefix="/api/v1", tags=["download"])

# 静的ファイル配信
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# ルートページ（Design原則: 61. 即座の喜びを与える）
@app.get("/", response_class=HTMLResponse)
async def root():
    """投稿フォームページ"""
    html_path = Path("app/static/index.html")
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))

# ヘルスチェック
@app.get("/health")
async def health_check():
    """システムヘルスチェック（監視用）"""
    return {
        "status": "healthy",
        "version": "0.1.0",
        "disk_free_gb": get_disk_free_space()
    }

def get_disk_free_space() -> float:
    """ディスク空き容量（GB）"""
    import shutil
    stat = shutil.disk_usage(settings.DATA_DIR)
    return stat.free / (1024**3)

# 起動時処理
@app.on_event("startup")
async def startup_event():
    logger.info("MultiLang Voice Lab starting...")
    # ディスク容量チェック（Design原則: 15. エラーを回避する）
    free_gb = get_disk_free_space()
    if free_gb < 50:
        logger.warning(f"Disk space low: {free_gb:.1f} GB remaining")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("MultiLang Voice Lab shutting down...")
