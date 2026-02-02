"""
ffmpeg/ffprobe ラッパー
Design原則: 18. 複雑性をシステム側へ
"""
import subprocess
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def get_audio_duration(audio_path: Path) -> float:
    """
    音声ファイルの長さ（秒）を取得
    """
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json",
            str(audio_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            raise RuntimeError(f"ffprobe failed: {result.stderr}")
        
        data = json.loads(result.stdout)
        duration = float(data["format"]["duration"])
        
        return duration
        
    except Exception as e:
        logger.error(f"Failed to get duration for {audio_path}: {e}")
        raise


def convert_audio(
    input_path: Path,
    output_path: Path,
    sample_rate: int = 16000,
    channels: int = 1,
    codec: str = "pcm_s16le"
) -> None:
    """
    音声フォーマット変換
    """
    try:
        cmd = [
            "ffmpeg", "-i", str(input_path),
            "-ar", str(sample_rate),
            "-ac", str(channels),
            "-c:a", codec,
            "-y",
            str(output_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg conversion failed: {result.stderr}")
        
        if not output_path.exists():
            raise FileNotFoundError("Converted audio not created")
        
    except Exception as e:
        logger.error(f"Failed to convert {input_path}: {e}")
        raise


def extract_audio_segment(
    input_path: Path,
    output_path: Path,
    start_sec: float,
    duration_sec: float
) -> None:
    """
    音声の一部を切り出し
    Design原則: 8. 直接操作 - 正確なタイムスタンプ
    """
    try:
        cmd = [
            "ffmpeg", "-i", str(input_path),
            "-ss", str(start_sec),
            "-t", str(duration_sec),
            "-c", "copy",
            "-y",
            str(output_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg segment extraction failed: {result.stderr}")
        
    except Exception as e:
        logger.error(f"Failed to extract segment: {e}")
        raise
