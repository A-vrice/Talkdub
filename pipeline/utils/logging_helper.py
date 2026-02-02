"""
構造化ログヘルパー
Design原則: 6. 一貫性 - ログ形式を統一
"""
import logging
from typing import Any
import json

class StructuredLogger:
    """
    構造化ログ（JSON形式）
    Design原則: 12. ユーザーの記憶に頼らない - job_id自動付与
    """
    
    def __init__(self, job_id: str, phase_name: str):
        self.job_id = job_id
        self.phase_name = phase_name
        self.logger = logging.getLogger(f"talkdub.{phase_name}")
    
    def _log(self, level: int, message: str, **extra):
        """構造化ログ出力"""
        log_data = {
            "job_id": self.job_id,
            "phase": self.phase_name,
            "message": message,
            **extra
        }
        self.logger.log(level, json.dumps(log_data, ensure_ascii=False))
    
    def info(self, message: str, **extra):
        self._log(logging.INFO, message, **extra)
    
    def warning(self, message: str, **extra):
        self._log(logging.WARNING, message, **extra)
    
    def error(self, message: str, **extra):
        self._log(logging.ERROR, message, **extra)
    
    def debug(self, message: str, **extra):
        self._log(logging.DEBUG, message, **extra)
    
    def progress(self, current: int, total: int, message: str = ""):
        """
        進捗ログ（Design原則: 65. 進捗を返す）
        """
        percent = (current / total * 100) if total > 0 else 0
        self.info(
            f"Progress: {message}",
            progress_current=current,
            progress_total=total,
            progress_percent=round(percent, 1)
        )
