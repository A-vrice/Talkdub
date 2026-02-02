"""
パイプライン統合オーケストレーター
Design原則: 23. オブジェクトベース - 対象中心に組む
"""
import logging
from typing import List, Type
from dataclasses import dataclass

from pipeline.base_phase import BasePhase, PhaseResult, PhaseError
from app.services.storage import update_job_status

logger = logging.getLogger(__name__)

@dataclass
class PipelineConfig:
    """パイプライン設定"""
    phases: List[Type[BasePhase]]
    stop_on_error: bool = True

class PipelineOrchestrator:
    """
    パイプライン実行オーケストレーター
    Design原則: 18. 複雑性をシステム側へ
    """
    
    def __init__(self, job_id: str, config: PipelineConfig):
        self.job_id = job_id
        self.config = config
        self.logger = logging.getLogger(f"Pipeline.{job_id}")
    
    def run(self) -> dict[str, PhaseResult]:
        """
        全Phase順次実行
        Returns: {Phase名: PhaseResult}
        """
        results = {}
        
        for phase_class in self.config.phases:
            phase = phase_class(self.job_id)
            phase_name = phase.get_phase_name()
            
            # ステータス更新
            update_job_status(
                job_id=self.job_id,
                status="PROCESSING",
                current_phase=phase_name
            )
            
            self.logger.info(f"Executing {phase_name}")
            
            try:
                result = phase.run()
                results[phase_name] = result
                
                if not result.success and self.config.stop_on_error:
                    self.logger.error(f"Pipeline stopped due to {phase_name} failure")
                    break
                    
            except Exception as e:
                self.logger.exception(f"Unexpected error in {phase_name}: {e}")
                results[phase_name] = PhaseResult(
                    success=False,
                    output_files={},
                    metadata={},
                    error=f"予期しないエラー: {str(e)}"
                )
                
                if self.config.stop_on_error:
                    break
        
        return results
    
    def get_summary(self, results: dict[str, PhaseResult]) -> dict:
        """パイプライン実行サマリー"""
        total = len(results)
        success_count = sum(1 for r in results.values() if r.success)
        total_duration = sum(r.duration_sec for r in results.values())
        
        return {
            "total_phases": total,
            "successful_phases": success_count,
            "failed_phases": total - success_count,
            "total_duration_sec": total_duration,
            "success_rate": success_count / total if total > 0 else 0
        }
