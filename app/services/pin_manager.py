"""
PIN管理（Redis永続化版）
Design原則: 54. フェールセーフ - 再起動に耐える
"""
import redis
import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional

from config.settings import settings

logger = logging.getLogger(__name__)

class PINManager:
    """PIN生成・検証管理（Redis永続化）"""
    
    def __init__(self):
        self.redis = redis.from_url(
            settings.CELERY_BROKER_URL,
            decode_responses=True
        )
        self.prefix = "talkdub:pin:"
    
    def generate_pin(self, job_id: str) -> str:
        """
        6桁PINコード生成
        Design原則: 13. コンストレイント - 6桁固定
        """
        pin = ''.join([str(secrets.randbelow(10)) for _ in range(6)])
        
        key = f"{self.prefix}{job_id}"
        expiry_seconds = settings.PIN_EXPIRY_HOURS * 3600
        
        # Redis HSET + EXPIRE
        self.redis.hset(key, mapping={
            "pin": pin,
            "attempts": "0",
            "created_at": datetime.utcnow().isoformat()
        })
        self.redis.expire(key, expiry_seconds)
        
        logger.info(f"PIN generated for job {job_id}, expires in {settings.PIN_EXPIRY_HOURS}h")
        return pin
    
    def verify_pin(self, job_id: str, pin: str) -> tuple[bool, str]:
        """
        PIN検証
        Returns: (成功/失敗, エラーメッセージ)
        Design原則: 15. エラーを回避する - 試行回数制限
        """
        key = f"{self.prefix}{job_id}"
        
        if not self.redis.exists(key):
            return False, "PINが見つかりません（有効期限切れの可能性があります）"
        
        data = self.redis.hgetall(key)
        stored_pin = data.get("pin")
        attempts = int(data.get("attempts", 0))
        
        # 試行回数チェック
        if attempts >= 5:
            return False, "試行回数上限に達しました"
        
        # 試行回数を増やす
        self.redis.hincrby(key, "attempts", 1)
        
        if stored_pin == pin:
            # 成功時は試行回数をリセット（再利用許可）
            self.redis.hset(key, "attempts", "0")
            return True, ""
        else:
            remaining = 5 - (attempts + 1)
            return False, f"PINコードが正しくありません（残り{remaining}回）"
    
    def delete_pin(self, job_id: str) -> None:
        """PIN削除（ジョブ削除時）"""
        key = f"{self.prefix}{job_id}"
        self.redis.delete(key)
    
    def cleanup_expired(self) -> int:
        """
        期限切れPINの削除（実際はRedisのEXPIREで自動削除）
        この関数は監視用
        """
        pattern = f"{self.prefix}*"
        count = 0
        
        for key in self.redis.scan_iter(match=pattern):
            if self.redis.ttl(key) == -1:  # 期限が設定されていない異常データ
                self.redis.delete(key)
                count += 1
        
        return count

# シングルトンインスタンス
pin_manager = PINManager()
