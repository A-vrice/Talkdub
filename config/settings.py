"""
設定管理: 環境変数と固定パラメータ
Design原則: 42. よいデフォルト - 妥当な初期値で操作を減らす
"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # プロジェクトルート
    BASE_DIR: Path = Path(__file__).parent.parent
    
    # データディレクトリ
    DATA_DIR: Path = BASE_DIR / "data"
    JOBS_DIR: Path = DATA_DIR / "jobs"
    REF_AUDIO_DIR: Path = DATA_DIR / "ref_audio"
    OUTPUT_DIR: Path = DATA_DIR / "output"
    TEMP_DIR: Path = DATA_DIR / "temp"
    LOGS_DIR: Path = DATA_DIR / "logs"
    
    # サーバー
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False
    
    # セキュリティ
    SECRET_KEY: str = os.getenv("SECRET_KEY", "CHANGE_ME_IN_PRODUCTION")
    CORS_ORIGINS: list = ["http://localhost:3000"]
    
    # レート制限（nginx側でも設定）
    RATE_LIMIT_SUBMISSIONS_PER_HOUR: int = 3
    RATE_LIMIT_DOWNLOADS_PER_MINUTE: int = 2
    
    # 外部API
    HF_TOKEN: str = os.getenv("HF_TOKEN", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    
    # 対応言語（10言語固定）
    SUPPORTED_LANGUAGES: list = ["ja", "zh", "en", "de", "fr", "it", "es", "pt", "ru", "ko"]
    
    # パイプラインパラメータ（v0.1固定値）
    ATEMPO_MAX: float = 1.3
    MAX_OVERLAP_SEC: float = 2.0
    MAX_OVERLAP_RATIO: float = 0.25
    OVERLAP_DUCK_DB: float = -6.0
    
    # チャンク設定（翻訳）
    CHUNK_CHAR_LIMIT_SRC: int = 2500
    CHUNK_SEG_LIMIT: int = 40
    MAX_RETRIES: int = 5
    BACKOFF_BASE_SEC: float = 2.0
    
    # 保持期限
    DELIVERY_RETENTION_HOURS: int = 72
    FAILED_JOB_RETENTION_DAYS: int = 7
    TEMP_FILE_RETENTION_HOURS: int = 48
    
    # メール通知
    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM: str = os.getenv("SMTP_FROM", "noreply@multilangvoicelab.local")
    
    # Celery
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()

# ディレクトリ自動作成
for directory in [
    settings.JOBS_DIR,
    settings.REF_AUDIO_DIR,
    settings.OUTPUT_DIR,
    settings.TEMP_DIR,
    settings.LOGS_DIR,
]:
    directory.mkdir(parents=True, exist_ok=True)
