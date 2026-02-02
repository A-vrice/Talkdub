"""
翻訳結果キャッシュ
Design原則: 14. プリコンピュテーション
"""
import hashlib
import json
import redis
from typing import Optional, List
from datetime import timedelta

from config.settings import settings

class TranslationCache:
    """
    翻訳結果キャッシュ（Redis）
    同一テキストの重複翻訳を回避してコスト削減
    """
    
    def __init__(self):
        self.redis = redis.from_url(
            settings.CELERY_BROKER_URL,
            decode_responses=True
        )
        self.prefix = "talkdub:translation_cache"
        self.enabled = settings.TRANSLATION_CACHE_ENABLED
        self.ttl = timedelta(hours=settings.TRANSLATION_CACHE_TTL_HOURS)
    
    def get(
        self,
        texts: List[str],
        src_lang: str,
        tgt_lang: str
    ) -> Optional[List[str]]:
        """
        キャッシュから翻訳取得
        
        Returns:
            キャッシュヒット時は翻訳リスト、ミス時はNone
        """
        if not self.enabled:
            return None
        
        cache_key = self._generate_key(texts, src_lang, tgt_lang)
        
        try:
            cached = self.redis.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass
        
        return None
    
    def set(
        self,
        texts: List[str],
        src_lang: str,
        tgt_lang: str,
        translations: List[str]
    ) -> None:
        """キャッシュに翻訳を保存"""
        if not self.enabled:
            return
        
        cache_key = self._generate_key(texts, src_lang, tgt_lang)
        
        try:
            self.redis.setex(
                cache_key,
                int(self.ttl.total_seconds()),
                json.dumps(translations, ensure_ascii=False)
            )
        except Exception:
            pass  # キャッシュ失敗は致命的ではない
    
    def _generate_key(
        self,
        texts: List[str],
        src_lang: str,
        tgt_lang: str
    ) -> str:
        """キャッシュキー生成"""
        # テキスト群をハッシュ化
        text_hash = hashlib.sha256(
            json.dumps(texts, ensure_ascii=False, sort_keys=True).encode()
        ).hexdigest()[:16]
        
        return f"{self.prefix}:{src_lang}:{tgt_lang}:{text_hash}"
    
    def get_stats(self) -> dict:
        """キャッシュ統計情報取得（監視用）"""
        pattern = f"{self.prefix}:*"
        keys = list(self.redis.scan_iter(match=pattern, count=100))
        
        return {
            "total_cached_entries": len(keys),
            "enabled": self.enabled
        }

# シングルトンインスタンス
translation_cache = TranslationCache()
