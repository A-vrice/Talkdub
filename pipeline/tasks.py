"""
Celeryタスク定義（リファクタ版）
Design原則: 2. 簡単にする - 手数を減らす
"""
import logging
from celery import Task
from datetime import datetime, timedelta

from app.services.job_queue import celery_app
from app.services.storage import load_job, save_job, update_job_status
from app.services.notification import send_job_completed_email, send_job_failed_email
from pipeline.orchestrator import PipelineOrchestrator, PipelineConfig
from config.settings import settings

logger = logging.getLogger(__name__)

class JobTask(Task):
    """カスタムタスククラス"""
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """タスク失敗時のフック"""
        job_id = args[0] if args else None
        if job_id:
            logger.error(f"Task failed for job {job_id}: {exc}")
            update_job_status(job_id, "FAILED", error=str(exc))
            
            job = load_job(job_id)
            send_job_failed_email(
                job_id=job_id,
                email=job["user_email"],
                error_message=str(exc)
            )

@celery_app.task(base=JobTask, bind=True)
def process_job_task(self, job_id: str):
    """メインジョブ処理タスク"""
    logger.info(f"Starting job {job_id}")
    
    try:
        # Phase定義
        from pipeline.phases.pre_0_download import DownloadPhase
        from pipeline.phases.pre_1_normalize import NormalizePhase
        from pipeline.phases.pre_2_separate import SeparatePhase
        from pipeline.phases.pre_3_whisperx import WhisperXPhase
        from pipeline.phases.pre_3_5_vad import VADPhase
        from pipeline.phases.pre_4_ref_audio import RefAudioPhase
        from pipeline.phases.pre_5_hallucination import HallucinationPhase
        # from pipeline.phases.trans_groq import TranslationPhase  # 次回実装
        # ... (TTS, Post処理は次回)
        
        # パイプライン設定
        config = PipelineConfig(
            phases=[
                DownloadPhase,
                NormalizePhase,
                SeparatePhase,
                WhisperXPhase,
                VADPhase,
                RefAudioPhase,
                HallucinationPhase,
                # TranslationPhase,  # 次回
                # TTSPhase,
                # ... (Post処理)
            ],
            stop_on_error=True
        )
        
        # オーケストレーター実行
        orchestrator = PipelineOrchestrator(job_id, config)
        results = orchestrator.run()
        
        # サマリー取得
        summary = orchestrator.get_summary(results)
        logger.info(f"Pipeline summary for job {job_id}: {summary}")
        
        # 全Phase成功チェック
        all_success = all(r.success for r in results.values())
        
        if not all_success:
            failed_phases = [name for name, r in results.items() if not r.success]
            raise RuntimeError(f"以下のPhaseが失敗しました: {', '.join(failed_phases)}")
        
        # 完了処理
        job = load_job(job_id)
        job["status"] = "COMPLETED"
        job["current_phase"] = None
        job["expires_at"] = (
            datetime.utcnow() + timedelta(hours=settings.DELIVERY_RETENTION_HOURS)
        ).isoformat() + "Z"
        save_job(job)
        
        # 完了メール送信
        download_url = f"{settings.PUBLIC_URL}/status/{job_id}"
        send_job_completed_email(
            job_id=job_id,
            email=job["user_email"],
            download_url=download_url,
            expires_at=job["expires_at"]
        )
        
        logger.info(f"Job {job_id} completed successfully")
        
    except Exception as e:
        logger.exception(f"Job {job_id} failed: {e}")
        raise
