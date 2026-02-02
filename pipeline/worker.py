"""
Celery Worker エントリーポイント
Design原則: 90. UIをロックしない - 非同期処理
"""
import logging
from app.services.job_queue import celery_app

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# タスクを自動検出
celery_app.autodiscover_tasks(['pipeline'])

if __name__ == '__main__':
    celery_app.start()
