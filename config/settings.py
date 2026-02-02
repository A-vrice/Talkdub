"""
設定管理 v0.1.4 - Groq API詳細設定追加
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

    # Pipeline Timeouts (秒)
    TIMEOUT_DOWNLOAD: int = 1800  # 30分
    TIMEOUT_NORMALIZE: int = 3600  # 1時間
    TIMEOUT_SEPARATE: int = 7200  # 2時間 (Demucs重い)
    TIMEOUT_WHISPERX: int = 10800  # 3時間
    TIMEOUT_VAD: int = 1800
    TIMEOUT_TTS_PER_SEGMENT: int = 300  # 5分/セグメント
    TIMEOUT_FFMPEG_BASIC: int = 300
    TIMEOUT_FFMPEG_COMPLEX: int = 3600
    
    # Phase Retry Settings
    PHASE_MAX_RETRIES: int = 3
    PHASE_RETRY_DELAY_SEC: float = 5.0
    
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

    # Groq API詳細設定
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    GROQ_MAX_RETRIES: int = 5
    GROQ_TIMEOUT_SEC: int = 30
    GROQ_RATE_LIMIT_RPM: int = 60  # Requests per minute
    GROQ_RATE_LIMIT_BUFFER: float = 0.9  # 90%までに抑える（安全マージン）

    # 翻訳プロンプト設定
    TRANSLATION_TEMPERATURE: float = 0.3  # 一貫性重視
    TRANSLATION_MAX_TOKENS: int = 4096
    TRANSLATION_SYSTEM_PROMPT_TEMPLATE: str = """You are a professional translator specialized in video subtitle translation.
Translate the following segments from {src_lang} to {tgt_lang}.

IMPORTANT RULES:
1. Preserve the meaning and tone (formal/casual) of the original text
2. Keep translations natural and concise for spoken dialogue
3. Maintain consistency in terminology throughout
4. DO NOT add explanations, notes, or extra content
5. If a segment is a sound effect (like [laugh], [music]), keep it as-is or translate appropriately
{context_instruction}"""

    # 翻訳品質チェック閾値
    TRANSLATION_MIN_LENGTH_RATIO: float = 0.1  # 元の10%未満は異常
    TRANSLATION_MAX_LENGTH_RATIO: float = 5.0  # 元の5倍超は異常
    TRANSLATION_SUSPICIOUS_PATTERNS: list[str] = [
        r'\\[.*?\\]',  # 未翻訳の記号（[laugh]等）が残っている
        r'[\u4e00-\u9fff]',  # 日本語→英語翻訳で漢字が残る
        r'[\u3040-\u309f\u30a0-\u30ff]',  # 日本語→英語翻訳でひらがな・カタカナが残る
    ]

    # チャンク分割設定
    CHUNK_CHAR_LIMIT_SRC: int = 2000  # 2500→2000に削減（安全マージン）
    CHUNK_SEG_LIMIT: int = 30  # 40→30に削減
    CHUNK_OVERLAP_SEGS: int = 2  # 前後のコンテキスト保持用オーバーラップ

    # 翻訳キャッシュ設定
    TRANSLATION_CACHE_ENABLED: bool = True
    TRANSLATION_CACHE_TTL_HOURS: int = 72  # 72時間キャッシュ保持
    
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
