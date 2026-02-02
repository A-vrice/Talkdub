"""
ジョブキュー管理（Celery）
Design原則: 18. 複雑性をシステム側へ
"""
from celery import Celery
import logging

from config.settings import settings

logger = logging.getLogger(__name__)

celery_app = Celery(
    "talkdub",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=86400,  # 24時間
    worker_prefetch_multiplier=1,  # 1ジョブずつ処理
)


def enqueue_job(job_id: str) -> str:
    """
    ジョブをキューへ追加
    Returns: Celery task_id
    """
    from pipeline.tasks import process_job_task
    
    result = process_job_task.delay(job_id)
    logger.info(f"Job {job_id} enqueued with task_id={result.id}")
    return result.id


def get_queue_length() -> int:
    """現在のキュー長を取得（監視用）"""
    inspect = celery_app.control.inspect()
    reserved = inspect.reserved()
    
    if not reserved:
        return 0
    
    total = sum(len(tasks) for tasks in reserved.values())
    return total
