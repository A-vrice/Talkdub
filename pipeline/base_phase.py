"""
Phase基底クラス v2（リファクタ版）
"""
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Any
from contextlib import contextmanager

from app.services.storage import load_job, save_job
from pipeline.phase_dependencies import PhaseID, validate_phase_preconditions
from pipeline.utils.logging_helper import StructuredLogger
from pipeline.utils.error_translator import ErrorTranslator
from config.settings import settings

@dataclass
class PhaseResult:
    """Phase処理結果"""
    success: bool
    output_files: dict[str, Path]
    meta dict[str, Any]
    error: Optional[str] = None
    user_friendly_error: Optional[str] = None  # 追加
    duration_sec: float = 0.0

class PhaseError(Exception):
    """Phase処理エラー"""
    pass

class BasePhase(ABC):
    """Phase処理の抽象基底クラス v2"""
    
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.temp_dir = settings.TEMP_DIR / job_id
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # 構造化ログ
        self.logger = StructuredLogger(job_id, self.get_phase_name())
    
    @abstractmethod
    def get_phase_name(self) -> str:
        """Phase名"""
        pass
    
    @abstractmethod
    def get_phase_id(self) -> PhaseID:
        """Phase識別子"""
        pass
    
    @abstractmethod
    def get_timeout(self) -> int:
        """タイムアウト時間（秒）"""
        pass
    
    @abstractmethod
    def execute(self) -> PhaseResult:
        """Phase処理本体"""
        pass
    
    def run(self, max_retries: int = None) -> PhaseResult:
        """
        Phase実行（事前検証 + リトライ + エラー翻訳）
        """
        max_retries = max_retries or settings.PHASE_MAX_RETRIES
        start_time = time.time()
        
        self.logger.info(f"Starting {self.get_phase_name()}")
        
        # 事前検証（Design原則: 32. 前提条件は先に提示する）
        job = load_job(self.job_id)
        is_valid, error_msg = validate_phase_preconditions(
            self.get_phase_id(),
            self.job_id,
            job,
            self.temp_dir
        )
        
        if not is_valid:
            self.logger.error(f"Precondition validation failed: {error_msg}")
            return PhaseResult(
                success=False,
                output_files={},
                metadata={},
                error=error_msg,
                user_friendly_error=error_msg  # 前提条件エラーは既にわかりやすい
            )
        
        # リトライループ
        last_error = None
        for attempt in range(max_retries):
            try:
                result = self.execute()
                result.duration_sec = time.time() - start_time
                
                self.logger.info(
                    f"Completed successfully",
                    attempt=attempt + 1,
                    duration_sec=round(result.duration_sec, 2)
                )
                
                # job.json更新
                self._update_job_metadata(result)
                
                return result
                
            except Exception as e:
                last_error = e
                self.logger.warning(
                    f"Failed",
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    error=str(e)
                )
                
                if attempt < max_retries - 1:
                    delay = settings.PHASE_RETRY_DELAY_SEC * (2 ** attempt)
                    self.logger.info(f"Retrying in {delay}s")
                    time.sleep(delay)
        
        # 全リトライ失敗
        technical_error = str(last_error)
        user_error = ErrorTranslator.translate(technical_error)
        
        self.logger.error(
            f"Failed after {max_retries} attempts",
            technical_error=technical_error,
            user_error=user_error
        )
        
        return PhaseResult(
            success=False,
            output_files={},
            metadata={},
            error=technical_error,
            user_friendly_error=user_error,
            duration_sec=time.time() - start_time
        )
    
    def _update_job_metadata(self, result: PhaseResult) -> None:
        """job.jsonにメタデータを反映"""
        if not result.meta
            return
        
        job = load_job(self.job_id)
        
        for key, value in result.metadata.items():
            if isinstance(value, dict) and key in job and isinstance(job[key], dict):
                job[key].update(value)
            else:
                job[key] = value
        
        save_job(job)
    
    @contextmanager
    def temporary_file(self, suffix: str = ".tmp"):
        """一時ファイルのコンテキストマネージャ"""
        temp_path = self.temp_dir / f"{self.get_phase_name().replace(':', '_')}_{suffix}"
        try:
            yield temp_path
        finally:
            if temp_path.exists():
                temp_path.unlink()
                self.logger.debug(f"Cleaned up temporary file: {temp_path.name}")
