"""
Celeryタスク定義
Design原則: 25. オブジェクトは自身の状態を体現する
"""
import logging
from celery import Task
from datetime import datetime, timedelta

from app.services.job_queue import celery_app
from app.services.storage import load_job, save_job, update_job_status
from app.services.notification import send_job_completed_email, send_job_failed_email
from config.settings import settings

logger = logging.getLogger(__name__)

class JobTask(Task):
    """カスタムタスククラス（エラーハンドリング統一）"""
    
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
    """
    メインジョブ処理タスク
    Design原則: 65. 進捗を返す
    """
    logger.info(f"Starting job {job_id}")
    
    try:
        # Phase Pre-0: ダウンロード
        from pipeline.phases.pre_0_download import phase_download
        update_job_status(job_id, "PROCESSING", current_phase="Pre-0: Download")
        phase_download(job_id)
        
        # Phase Pre-1: 正規化
        from pipeline.phases.pre_1_normalize import phase_normalize
        update_job_status(job_id, "PROCESSING", current_phase="Pre-1: Normalize")
        phase_normalize(job_id)
        
        # Phase Pre-2: BGM分離
        from pipeline.phases.pre_2_separate import phase_separate
        update_job_status(job_id, "PROCESSING", current_phase="Pre-2: Separate")
        phase_separate(job_id)
        
        # Phase Pre-3: WhisperX
        from pipeline.phases.pre_3_whisperx import phase_whisperx
        update_job_status(job_id, "PROCESSING", current_phase="Pre-3: WhisperX")
        phase_whisperx(job_id)
        
        # Phase Pre-3.5: Silero VAD
        from pipeline.phases.pre_3_5_vad import phase_vad
        update_job_status(job_id, "PROCESSING", current_phase="Pre-3.5: VAD")
        phase_vad(job_id)
        
        # Phase Pre-4: ref_audio抽出
        from pipeline.phases.pre_4_ref_audio import phase_ref_audio
        update_job_status(job_id, "PROCESSING", current_phase="Pre-4: RefAudio")
        phase_ref_audio(job_id)
        
        # Phase Pre-5: ハルシネーション判定
        from pipeline.phases.pre_5_hallucination import phase_hallucination
        update_job_status(job_id, "PROCESSING", current_phase="Pre-5: Hallucination")
        phase_hallucination(job_id)
        
        # Translation: Groq API
        from pipeline.phases.trans_groq import phase_translation
        update_job_status(job_id, "PROCESSING", current_phase="Translation")
        phase_translation(job_id)
        
        # TTS: Qwen3-TTS
        from pipeline.phases.tts_qwen import phase_tts
        update_job_status(job_id, "PROCESSING", current_phase="TTS")
        phase_tts(job_id)
        
        # Post-1: タイムライン計算
        from pipeline.phases.post_1_timeline import phase_timeline
        update_job_status(job_id, "PROCESSING", current_phase="Post-1: Timeline")
        phase_timeline(job_id)
        
        # Post-2: 音声結合
        from pipeline.phases.post_2_mix import phase_mix
        update_job_status(job_id, "PROCESSING", current_phase="Post-2: Mix")
        phase_mix(job_id)
        
        # Post-3: 動画尺一致
        from pipeline.phases.post_3_finalize import phase_finalize
        update_job_status(job_id, "PROCESSING", current_phase="Post-3: Finalize")
        phase_finalize(job_id)
        
        # Post-4: manifest/segments出力
        from pipeline.phases.post_4_manifest import phase_manifest
        update_job_status(job_id, "PROCESSING", current_phase="Post-4: Manifest")
        phase_manifest(job_id)
        
        # 完了処理
        job = load_job(job_id)
        job["status"] = "COMPLETED"
        job["current_phase"] = None
        job["expires_at"] = (datetime.utcnow() + timedelta(hours=settings.DELIVERY_RETENTION_HOURS)).isoformat() + "Z"
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
