"""
Phase Pre-1: 音声正規化
Design原則: 14. プリコンピュテーション - 最適値のプリセット
"""
import subprocess
import logging
from pathlib import Path

from config.settings import settings
from app.services.storage import load_job

logger = logging.getLogger(__name__)

def phase_normalize(job_id: str) -> None:
    """
    音声を16kHz mono, -23 LUFS に正規化
    
    入力: temp/{job_id}/original.wav
    成果物: temp/{job_id}/normalized.wav
    """
    temp_dir = settings.TEMP_DIR / job_id
    input_path = temp_dir / "original.wav"
    output_path = temp_dir / "normalized.wav"
    
    if not input_path.exists():
        raise FileNotFoundError("original.wav not found")
    
    try:
        # ffmpeg で正規化
        # Design原則: 42. よいデフォルト（-23 LUFS は業界標準）
        cmd = [
            "ffmpeg", "-i", str(input_path),
            "-af", "loudnorm=I=-23:TP=-2:LRA=7,aresample=16000",
            "-ac", "1",
            "-ar", "16000",
            "-y",
            str(output_path)
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg normalization failed: {result.stderr}")
        
        if not output_path.exists():
            raise FileNotFoundError("Normalized audio not created")
        
        logger.info(f"Phase Pre-1 completed for job {job_id}")
        
        # original.wav削除（ディスク節約）
        input_path.unlink()
        
    except subprocess.TimeoutExpired:
        raise RuntimeError("正規化がタイムアウトしました")
    except Exception as e:
        logger.error(f"Phase Pre-1 failed for job {job_id}: {e}")
        raise
