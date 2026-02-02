"""
Groq APIレート制限管理
Design原則: 15. エラーを回避する
"""
import time
import redis
from datetime import datetime, timedelta
from typing import Optional

from config.settings import settings

class RateLimiter:
    """
    Groq APIレート制限管理（Redis分散ロック）
    Design原則: 18. 複雑性をシステム側へ
    """
    
    def __init__(self):
        self.redis = redis.from_url(
            settings.CELERY_BROKER_URL,
            decode_responses=True
        )
        self.prefix = "talkdub:rate_limit:groq"
        self.rpm_limit = int(settings.GROQ_RATE_LIMIT_RPM * settings.GROQ_RATE_LIMIT_BUFFER)
    
    def acquire(self, timeout: float = 60.0) -> bool:
        """
        レート制限の範囲内でリクエストを許可
        
        Args:
            timeout: 最大待機時間（秒）
        
        Returns:
            許可された場合True、タイムアウト時False
        """
        start = time.time()
        
        while time.time() - start < timeout:
            # 現在の分のキー
            current_minute = datetime.utcnow().strftime("%Y%m%d%H%M")
            key = f"{self.prefix}:{current_minute}"
            
            # 現在のリクエスト数を取得
            current_count = self.redis.get(key)
            
            if current_count is None:
                # 新しい分の最初のリクエスト
                pipe = self.redis.pipeline()
                pipe.set(key, 1)
                pipe.expire(key, 120)  # 2分で自動削除
                pipe.execute()
                return True
            
            current_count = int(current_count)
            
            if current_count < self.rpm_limit:
                # まだ余裕がある
                self.redis.incr(key)
                return True
            
            # レート制限に達した、次の分まで待機
            wait_time = 60 - datetime.utcnow().second
            if wait_time > 0:
                time.sleep(min(wait_time, timeout - (time.time() - start)))
        
        return False
    
    def get_current_usage(self) -> dict:
        """現在のレート制限使用状況取得（監視用）"""
        current_minute = datetime.utcnow().strftime("%Y%m%d%H%M")
        key = f"{self.prefix}:{current_minute}"
        
        current_count = self.redis.get(key)
        current_count = int(current_count) if current_count else 0
        
        return {
            "current_requests": current_count,
            "limit": self.rpm_limit,
            "remaining": max(0, self.rpm_limit - current_count),
            "usage_percent": round(current_count / self.rpm_limit * 100, 1)
        }

# シングルトンインスタンス
groq_rate_limiter = RateLimiter()
