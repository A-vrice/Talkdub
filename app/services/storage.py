"""
ファイルストレージ管理
Design原則: 23. オブジェクトベースにする
"""
import json
import shutil
from pathlib import Path
from typing import Optional
from datetime import datetime
import logging

from config.settings import settings

logger = logging.getLogger(__name__)

class JobNotFoundError(Exception):
    """ジョブが見つからない"""
    pass

class JobStorageError(Exception):
    """ストレージ操作エラー"""
    pass


def job_exists(job_id: str) -> bool:
    """ジョブの存在確認"""
    return (settings.JOBS_DIR / f"{job_id}.json").exists()


def load_job(job_id: str) -> dict:
    """
    ジョブデータ読み込み
    Raises: JobNotFoundError
    """
    job_path = settings.JOBS_DIR / f"{job_id}.json"
    
    if not job_path.exists():
        raise JobNotFoundError(f"Job {job_id} not found")
    
    try:
        return json.loads(job_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse job {job_id}: {e}")
        raise JobStorageError(f"Corrupted job file: {job_id}")


def save_job(job: dict, atomic: bool = True) -> None:
    """
    ジョブデータ保存
    Design原則: 54. フェールセーフ - atomic writeで破損防止
    """
    job_id = job["job_id"]
    job_path = settings.JOBS_DIR / f"{job_id}.json"
    
    try:
        if atomic:
            # Design原則: 15. エラーを回避する（atomic write）
            temp_path = job_path.with_suffix(".tmp")
            temp_path.write_text(
                json.dumps(job, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
            temp_path.replace(job_path)  # atomic on POSIX
        else:
            job_path.write_text(
                json.dumps(job, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
            
        logger.debug(f"Job {job_id} saved successfully")
        
    except Exception as e:
        logger.error(f"Failed to save job {job_id}: {e}")
        raise JobStorageError(f"Failed to save job: {e}")


def update_job_status(
    job_id: str,
    status: str,
    current_phase: Optional[str] = None,
    error: Optional[str] = None
) -> None:
    """
    ジョブステータス更新（便利関数）
    Design原則: 18. 複雑性をシステム側へ
    """
    job = load_job(job_id)
    job["status"] = status
    
    if current_phase:
        job["current_phase"] = current_phase
    
    if error:
        job["error"] = error
    
    save_job(job)


def delete_job(job_id: str, keep_logs: bool = True) -> None:
    """
    ジョブとその関連ファイルを削除
    Design原則: 54. フェールセーフ - ログは保持
    """
    try:
        # job.json
        job_path = settings.JOBS_DIR / f"{job_id}.json"
        if job_path.exists():
            job_path.unlink()
        
        # ref_audio
        ref_dir = settings.REF_AUDIO_DIR / job_id
        if ref_dir.exists():
            shutil.rmtree(ref_dir)
        
        # output
        output_dir = settings.OUTPUT_DIR / job_id
        if output_dir.exists():
            shutil.rmtree(output_dir)
        
        # temp
        temp_dir = settings.TEMP_DIR / job_id
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        
        # logs（keep_logsがFalseの時だけ削除）
        if not keep_logs:
            log_dir = settings.LOGS_DIR / job_id
            if log_dir.exists():
                shutil.rmtree(log_dir)
        
        logger.info(f"Job {job_id} deleted successfully (keep_logs={keep_logs})")
        
    except Exception as e:
        logger.error(f"Failed to delete job {job_id}: {e}")
        raise JobStorageError(f"Failed to delete job: {e}")


def get_expired_jobs() -> list[str]:
    """
    期限切れジョブのリストを取得
    Design原則: 29. 唯一の選択は自動化する
    """
    expired = []
    now = datetime.utcnow()
    
    for job_file in settings.JOBS_DIR.glob("*.json"):
        try:
            job = json.loads(job_file.read_text())
            
            if job.get("expires_at"):
                expires = datetime.fromisoformat(job["expires_at"].replace("Z", "+00:00"))
                if now > expires:
                    expired.append(job["job_id"])
                    
        except Exception as e:
            logger.warning(f"Failed to check expiry for {job_file.name}: {e}")
    
    return expired


def cleanup_temp_files(hours: int = 48) -> int:
    """
    古い一時ファイルを削除
    Returns: 削除したディレクトリ数
    """
    count = 0
    cutoff = datetime.utcnow().timestamp() - (hours * 3600)
    
    for temp_dir in settings.TEMP_DIR.iterdir():
        if temp_dir.is_dir() and temp_dir.stat().st_mtime < cutoff:
            try:
                shutil.rmtree(temp_dir)
                count += 1
            except Exception as e:
                logger.warning(f"Failed to delete temp dir {temp_dir}: {e}")
    
    return count
