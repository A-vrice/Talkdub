"""
Phase処理基底クラス
Design原則: 6. 一貫性 - 挙動のルールを統一
"""
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Any
from contextlib import contextmanager

from app.services.storage import load_job, save_job
from config.settings import settings

logger = logging.getLogger(__name__)

@dataclass
class PhaseResult:
    """Phase処理結果（Design原則: 25. 状態を体現する）"""
    success: bool
    output_files: dict[str, Path]  # キー: 成果物名, 値: ファイルパス
    meta dict[str, Any]  # job.json更新用メタデータ
    error: Optional[str] = None
    duration_sec: float = 0.0

class PhaseError(Exception):
    """Phase処理エラー"""
    pass

class BasePhase(ABC):
    """
    Phase処理の抽象基底クラス
    
    全Phaseで共通のエラーハンドリング、ログ、リトライを提供
    Design原則: 18. 複雑性をシステム側へ
    """
    
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.logger = self._setup_logger()
        self.temp_dir = settings.TEMP_DIR / job_id
        self.temp_dir.mkdir(parents=True, exist_ok=True)
    
    def _setup_logger(self) -> logging.Logger:
        """構造化ログの準備"""
        phase_logger = logging.getLogger(f"{self.__class__.__name__}.{self.job_id}")
        return phase_logger
    
    @abstractmethod
    def get_phase_name(self) -> str:
        """Phase名（例: "Pre-0: Download"）"""
        pass
    
    @abstractmethod
    def get_timeout(self) -> int:
        """タイムアウト時間（秒）"""
        pass
    
    @abstractmethod
    def execute(self) -> PhaseResult:
        """Phase処理本体（サブクラスで実装）"""
        pass
    
    @abstractmethod
    def validate_inputs(self) -> None:
        """入力ファイル/データの検証（実行前）"""
        pass
    
    @abstractmethod
    def validate_outputs(self, result: PhaseResult) -> None:
        """成果物の検証（実行後）"""
        pass
    
    def run(self, max_retries: int = None) -> PhaseResult:
        """
        Phase実行（リトライ・エラーハンドリング込み）
        Design原則: 54. フェールセーフ - 取り消し可能性
        """
        max_retries = max_retries or settings.PHASE_MAX_RETRIES
        start_time = time.time()
        
        self.logger.info(f"Starting {self.get_phase_name()} for job {self.job_id}")
        
        # 入力検証
        try:
            self.validate_inputs()
        except Exception as e:
            self.logger.error(f"Input validation failed: {e}")
            return PhaseResult(
                success=False,
                output_files={},
                metadata={},
                error=f"入力検証失敗: {str(e)}"
            )
        
        # リトライループ
        last_error = None
        for attempt in range(max_retries):
            try:
                result = self.execute()
                result.duration_sec = time.time() - start_time
                
                # 成果物検証
                self.validate_outputs(result)
                
                self.logger.info(
                    f"{self.get_phase_name()} completed successfully "
                    f"(attempt {attempt + 1}/{max_retries}, duration={result.duration_sec:.2f}s)"
                )
                
                # job.json更新
                self._update_job_metadata(result)
                
                return result
                
            except Exception as e:
                last_error = e
                self.logger.warning(
                    f"{self.get_phase_name()} failed (attempt {attempt + 1}/{max_retries}): {e}"
                )
                
                if attempt < max_retries - 1:
                    delay = settings.PHASE_RETRY_DELAY_SEC * (2 ** attempt)  # 指数バックオフ
                    self.logger.info(f"Retrying in {delay}s...")
                    time.sleep(delay)
        
        # 全リトライ失敗
        self.logger.error(f"{self.get_phase_name()} failed after {max_retries} attempts")
        return PhaseResult(
            success=False,
            output_files={},
            metadata={},
            error=f"最大リトライ回数超過: {str(last_error)}",
            duration_sec=time.time() - start_time
        )
    
    def _update_job_metadata(self, result: PhaseResult) -> None:
        """job.jsonにメタデータを反映"""
        if not result.meta
            return
        
        job = load_job(self.job_id)
        
        # メタデータをマージ（深いマージ）
        for key, value in result.metadata.items():
            if isinstance(value, dict) and key in job and isinstance(job[key], dict):
                job[key].update(value)
            else:
                job[key] = value
        
        save_job(job)
    
    @contextmanager
    def temporary_file(self, suffix: str = ".tmp"):
        """一時ファイルのコンテキストマネージャ（自動削除）"""
        temp_path = self.temp_dir / f"{self.get_phase_name().replace(':', '_')}_{suffix}"
        try:
            yield temp_path
        finally:
            if temp_path.exists():
                temp_path.unlink()
                self.logger.debug(f"Cleaned up temporary file: {temp_path}")
