"""
Phase Pre-0: YouTube動画ダウンロード
Design原則: 15. エラーを回避する
"""
import subprocess
import logging
from pathlib import Path

from config.settings import settings
from app.services.storage import load_job, save_job
from pipeline.utils.ffmpeg import get_audio_duration

logger = logging.getLogger(__name__)

def phase_download(job_id: str) -> None:
    """
    YouTube動画から音声を抽出してダウンロード
    
    成果物:
    - temp/{job_id}/original.wav (元音声)
    - job.json の media.duration_sec 更新
    """
    job = load_job(job_id)
    video_url = job["source"]["url"]
    
    temp_dir = settings.TEMP_DIR / job_id
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = temp_dir / "original.wav"
    
    try:
        # yt-dlp でダウンロード + ffmpeg で wav変換
        # Design原則: 29. 唯一の選択は自動化する
        cmd = [
            "yt-dlp",
            "--extract-audio",
            "--audio-format", "wav",
            "--audio-quality", "0",
            "--output", str(output_path.with_suffix('.%(ext)s')),
            "--no-playlist",
            "--no-warnings",
            video_url
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=1800  # 30分タイムアウト
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"yt-dlp failed: {result.stderr}")
        
        if not output_path.exists():
            raise FileNotFoundError("Downloaded audio file not found")
        
        # メタデータ取得（動画尺）
        duration = get_audio_duration(output_path)
        
        # job.json更新
        job["media"]["duration_sec"] = duration
        save_job(job)
        
        logger.info(f"Phase Pre-0 completed for job {job_id}, duration={duration:.2f}s")
        
    except subprocess.TimeoutExpired:
        raise RuntimeError("ダウンロードがタイムアウトしました（動画が長すぎる可能性があります）")
    except Exception as e:
        logger.error(f"Phase Pre-0 failed for job {job_id}: {e}")
        raise
