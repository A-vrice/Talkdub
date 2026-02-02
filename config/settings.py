"""
設定管理 v0.1.1 - リファクタ版
Design原則: 42. よいデフォルト
"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Literal

class Settings(BaseSettings):
    # プロジェクト
    PROJECT_NAME: str = "TalkDub"
    VERSION: str = "0.1.1"
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
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    ENVIRONMENT: Literal["development", "production"] = os.getenv("ENVIRONMENT", "production")
    
    # セキュリティ
    SECRET_KEY: str = os.getenv("SECRET_KEY", "CHANGE_ME_IN_PRODUCTION")
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "https://talkdub.lab"]
    
    # レート制限
    RATE_LIMIT_SUBMISSIONS_PER_HOUR: int = 3
    RATE_LIMIT_DOWNLOADS_PER_MINUTE: int = 2
    RATE_LIMIT_STATUS_PER_MINUTE: int = 10
    
    # 外部API
    HF_TOKEN: str = os.getenv("HF_TOKEN", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    RESEND_API_KEY: str = os.getenv("RESEND_API_KEY", "")
    
    # メール設定
    EMAIL_FROM: str = "TalkDub <noreply@talkdub.lab>"
    EMAIL_REPLY_TO: str = "support@talkdub.lab"
    
    # 対応言語（10言語固定）
    SUPPORTED_LANGUAGES: dict[str, str] = {
        "ja": "日本語",
        "zh": "中文",
        "en": "English",
        "de": "Deutsch",
        "fr": "Français",
        "it": "Italiano",
        "es": "Español",
        "pt": "Português",
        "ru": "Русский",
        "ko": "한국어"
    }
    
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
    PIN_EXPIRY_HOURS: int = 72
    
    # Celery
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
    
    # Cloudflared Tunnel（追加仕様）
    CLOUDFLARED_ENABLED: bool = os.getenv("CLOUDFLARED_ENABLED", "false").lower() == "true"
    CLOUDFLARED_TUNNEL_ID: str = os.getenv("CLOUDFLARED_TUNNEL_ID", "")
    PUBLIC_URL: str = os.getenv("PUBLIC_URL", "https://talkdub.lab")
    
    # 監視・アラート
    SLACK_WEBHOOK_URL: str = os.getenv("SLACK_WEBHOOK_URL", "")
    ALERT_DISK_THRESHOLD_GB: float = 50.0
    ALERT_FAILURE_RATE_THRESHOLD: float = 0.3  # 30%
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        
    def model_post_init(self, __context) -> None:
        """ディレクトリ自動作成"""
        for directory in [
            self.JOBS_DIR,
            self.REF_AUDIO_DIR,
            self.OUTPUT_DIR,
            self.TEMP_DIR,
            self.LOGS_DIR,
        ]:
            directory.mkdir(parents=True, exist_ok=True)

settings = Settings()
