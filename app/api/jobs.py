"""
ジョブ投稿・ステータス確認API
Design原則: 32. 前提条件は先に提示する、55. エラー表示は建設的にする
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, HttpUrl, EmailStr, validator
from slowapi import Limiter
from slowapi.util import get_remote_address
import uuid
import re
from datetime import datetime, timedelta
import json

from config.settings import settings
from app.services.job_queue import enqueue_job
from app.services.storage import load_job, job_exists

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

class JobSubmission(BaseModel):
    """ジョブ投稿リクエスト（Design原則: 40. ストーリー性を持たせる）"""
    video_url: HttpUrl
    src_lang: str
    tgt_lang: str
    email: EmailStr
    webhook_url: HttpUrl | None = None
    
    @validator('src_lang', 'tgt_lang')
    def validate_language(cls, v):
        if v not in settings.SUPPORTED_LANGUAGES:
            raise ValueError(
                f"言語コード '{v}' は対応していません。対応言語: {', '.join(settings.SUPPORTED_LANGUAGES)}"
            )
        return v
    
    @validator('video_url')
    def validate_youtube_url(cls, v):
        """YouTube URL検証（Design原則: 50. 厳密さを求めない）"""
        url_str = str(v)
        patterns = [
            r'youtube\.com/watch\?v=',
            r'youtu\.be/',
            r'youtube\.com/embed/'
        ]
        if not any(re.search(p, url_str) for p in patterns):
            raise ValueError("YouTube URLの形式が正しくありません")
        return v

@router.post("/jobs", status_code=202)
@limiter.limit(f"{settings.RATE_LIMIT_SUBMISSIONS_PER_HOUR}/hour")
async def create_job(request: Request, submission: JobSubmission):
    """
    ジョブ投稿エンドポイント
    Design原則: 29. 唯一の選択は自動化する
    """
    # video_idを抽出
    video_id = extract_youtube_video_id(str(submission.video_url))
    if not video_id:
        raise HTTPException(
            status_code=400,
            detail="YouTube動画IDの抽出に失敗しました"
        )
    
    # 重複チェック（24時間以内の同一URL）
    # Design原則: 39. 整合性を損なう操作を求めない
    existing = check_duplicate_submission(video_id, hours=24)
    if existing:
        return {
            "job_id": existing,
            "status": "ALREADY_QUEUED",
            "message": "この動画は既に処理中または処理済みです",
            "status_url": f"/api/v1/jobs/{existing}/status"
        }
    
    # job_id生成
    job_id = str(uuid.uuid4())
    
    # job.json初期化
    job_data = {
        "schema_version": "0.1",
        "job_id": job_id,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "status": "QUEUED",
        "current_phase": None,
        
        "source": {
            "platform": "youtube",
            "video_id": video_id,
            "url": str(submission.video_url)
        },
        
        "languages": {
            "src_lang": submission.src_lang,
            "tgt_lang": submission.tgt_lang
        },
        
        "media": {
            "duration_sec": None,
            "audio_format": {
                "sample_rate_hz": 16000,
                "channels": 1
            }
        },
        
        "pipeline_params": {
            "max_atempo": settings.ATEMPO_MAX,
            "max_overlap_sec": settings.MAX_OVERLAP_SEC,
            "max_overlap_ratio": settings.MAX_OVERLAP_RATIO,
            "overlap_duck_db": settings.OVERLAP_DUCK_DB,
            "hallucination_policy": "silence",
            "timeline_reference": "ffprobe"
        },
        
        "speakers": [],
        "segments": [],
        
        "outputs": {
            "dub_wav": None,
            "manifest_json": None,
            "segments_json": None
        },
        
        "error": None,
        "progress": {
            "completed_segments": 0,
            "total_segments": 0,
            "percent": 0
        },
        
        "user_email": submission.email,
        "download_count": 0,
        "expires_at": None
    }
    
    # job.json保存
    job_path = settings.JOBS_DIR / f"{job_id}.json"
    job_path.write_text(json.dumps(job_data, indent=2, ensure_ascii=False))
    
    # キューへ追加（Celery）
    enqueue_job(job_id)
    
    # Design原則: 66. 操作の近くでフィードバック
    return {
        "job_id": job_id,
        "status": "QUEUED",
        "estimated_completion": (datetime.utcnow() + timedelta(hours=24)).isoformat() + "Z",
        "status_url": f"/api/v1/jobs/{job_id}/status",
        "download_url": f"/api/v1/jobs/{job_id}/download",
        "message": "ジョブを受け付けました。処理完了時にメールで通知します。"
    }

@router.get("/jobs/{job_id}/status")
async def get_job_status(job_id: str):
    """
    ステータス確認エンドポイント
    Design原則: 25. オブジェクトは自身の状態を体現する
    """
    if not job_exists(job_id):
        raise HTTPException(status_code=404, detail="ジョブが見つかりません")
    
    job = load_job(job_id)
    
    # Design原則: 28. データよりも情報を伝える
    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "current_phase": job.get("current_phase"),
        "progress": job["progress"],
        "created_at": job["created_at"],
        "estimated_completion": calculate_eta(job),
        "download_available": job["status"] == "COMPLETED",
        "download_expires_at": job.get("expires_at"),
        "error": job.get("error")
    }

def extract_youtube_video_id(url: str) -> str | None:
    """YouTube URLから動画IDを抽出"""
    patterns = [
        r'[?&]v=([^&]+)',
        r'youtu\.be/([^?]+)',
        r'embed/([^?]+)'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def check_duplicate_submission(video_id: str, hours: int = 24) -> str | None:
    """重複投稿チェック（同一video_idで指定時間内）"""
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    for job_file in settings.JOBS_DIR.glob("*.json"):
        job = json.loads(job_file.read_text())
        if job["source"]["video_id"] == video_id:
            created = datetime.fromisoformat(job["created_at"].replace("Z", "+00:00"))
            if created > cutoff:
                return job["job_id"]
    return None

def calculate_eta(job: dict) -> str:
    """処理完了予測時刻（Design原則: 28. 情報を伝える）"""
    if job["status"] == "COMPLETED":
        return job["created_at"]
    
    # 簡易版: created_at + 24時間
    created = datetime.fromisoformat(job["created_at"].replace("Z", "+00:00"))
    eta = created + timedelta(hours=24)
    return eta.isoformat() + "Z"
