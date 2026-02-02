"""
Groq API クライアント v2（リファクタ版）
Design原則: 18. 複雑性をシステム側へ
"""
import time
import logging
from typing import Optional, List, Dict
from groq import Groq, RateLimitError, APIError, APIConnectionError
from groq.types.chat import ChatCompletion

from config.settings import settings
from pipeline.utils.rate_limiter import groq_rate_limiter
from pipeline.utils.translation_cache import translation_cache
from pipeline.utils.translation_validator import TranslationValidator

logger = logging.getLogger(__name__)

class GroqAPIError(Exception):
    """Groq API エラー"""
    pass

class GroqClient:
    """Groq APIラッパー v2"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.GROQ_API_KEY
        if not self.api_key:
            raise GroqAPIError("GROQ_API_KEY not set")
        
        self.client = Groq(api_key=self.api_key)
        self.model = settings.GROQ_MODEL
        
        # 統計情報
        self.stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "total_tokens": 0,
            "total_cost_usd": 0.0  # 概算
        }
    
    def translate(
        self,
        texts: List[str],
        src_lang: str,
        tgt_lang: str,
        context: Optional[str] = None,
        max_retries: int = None
    ) -> List[str]:
        """
        テキスト一括翻訳（キャッシュ・レート制限対応）
        """
        max_retries = max_retries or settings.GROQ_MAX_RETRIES
        
        # キャッシュチェック
        cached = translation_cache.get(texts, src_lang, tgt_lang)
        if cached:
            self.stats["cache_hits"] += 1
            logger.info(f"Translation cache hit for {len(texts)} segments")
            return cached
        
        self.stats["cache_misses"] += 1
        
        # システムプロンプト生成
        system_prompt = self._build_system_prompt(src_lang, tgt_lang, context)
        user_prompt = self._build_user_prompt(texts)
        
        # リトライループ
        for attempt in range(max_retries):
            try:
                # レート制限取得
                if not groq_rate_limiter.acquire(timeout=60.0):
                    raise GroqAPIError("Rate limit acquisition timeout")
                
                # API呼び出し
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=settings.TRANSLATION_TEMPERATURE,
                    max_tokens=settings.TRANSLATION_MAX_TOKENS,
                    response_format={"type": "json_object"}
                )
                
                self.stats["total_requests"] += 1
                
                # トークン数・コスト記録
                if hasattr(response, 'usage'):
                    tokens = response.usage.total_tokens
                    self.stats["total_tokens"] += tokens
                    # llama-3.3-70b: $0.79/1M input tokens, $0.99/1M output tokens（概算）
                    self.stats["total_cost_usd"] += (tokens / 1_000_000) * 0.89
                
                # レスポンスパース
                translations = self._parse_response(response, len(texts))
                
                # 品質検証
                is_valid, warnings = TranslationValidator.validate(
                    texts, translations, src_lang, tgt_lang
                )
                
                if warnings:
                    for warning in warnings[:5]:  # 最初の5件のみログ
                        logger.warning(warning)
                
                if not is_valid:
                    raise GroqAPIError(
                        f"Translation quality validation failed: {len(warnings)} issues"
                    )
                
                # キャッシュ保存
                translation_cache.set(texts, src_lang, tgt_lang, translations)
                
                return translations
                
            except RateLimitError as e:
                # Groq APIのレート制限エラー
                logger.warning(f"Groq rate limit hit (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(60)  # 1分待機
                else:
                    raise GroqAPIError(f"Rate limit exceeded: {str(e)}")
            
            except APIConnectionError as e:
                # ネットワークエラー
                logger.warning(f"Groq API connection error (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    delay = settings.BACKOFF_BASE_SEC * (2 ** attempt)
                    time.sleep(delay)
                else:
                    raise GroqAPIError(f"Connection failed: {str(e)}")
            
            except APIError as e:
                # Groq APIエラー（4xx/5xx）
                logger.error(f"Groq API error (attempt {attempt + 1}): {e}")
                
                # 4xxエラー（クライアント側の問題）はリトライしない
                if hasattr(e, 'status_code') and 400 <= e.status_code < 500:
                    raise GroqAPIError(f"Client error: {str(e)}")
                
                # 5xxエラーはリトライ
                if attempt < max_retries - 1:
                    delay = settings.BACKOFF_BASE_SEC * (2 ** attempt)
                    time.sleep(delay)
                else:
                    raise GroqAPIError(f"API error: {str(e)}")
            
            except Exception as e:
                logger.warning(f"Unexpected error (attempt {attempt + 1}): {e}")
                
                if attempt < max_retries - 1:
                    delay = settings.BACKOFF_BASE_SEC * (2 ** attempt)
                    time.sleep(delay)
                else:
                    raise GroqAPIError(f"Translation failed: {str(e)}")
    
    def translate_shortened(
        self,
        text: str,
        src_lang: str,
        tgt_lang: str,
        max_length: int,
        max_retries: int = None
    ) -> str:
        """短縮翻訳（Post処理用）"""
        # ... (前回と同じ、レート制限追加)
        max_retries = max_retries or settings.GROQ_MAX_RETRIES
        
        for attempt in range(max_retries):
            try:
                if not groq_rate_limiter.acquire(timeout=60.0):
                    raise GroqAPIError("Rate limit acquisition timeout")
                
                # ... (以下前回と同じ)
                
            except RateLimitError:
                if attempt < max_retries - 1:
                    time.sleep(60)
                else:
                    raise GroqAPIError("Rate limit exceeded")
    
    def _build_system_prompt(
        self,
        src_lang: str,
        tgt_lang: str,
        context: Optional[str]
    ) -> str:
        """システムプロンプト生成"""
        lang_names = {
            "ja": "Japanese", "zh": "Chinese", "en": "English",
            "de": "German", "fr": "French", "it": "Italian",
            "es": "Spanish", "pt": "Portuguese", "ru": "Russian", "ko": "Korean"
        }
        
        src_name = lang_names.get(src_lang, src_lang)
        tgt_name = lang_names.get(tgt_lang, tgt_lang)
        
        context_instruction = ""
        if context:
            context_instruction = f"\n6. Context: This is from a video about '{context}'"
        
        return settings.TRANSLATION_SYSTEM_PROMPT_TEMPLATE.format(
            src_lang=src_name,
            tgt_lang=tgt_name,
            context_instruction=context_instruction
        )
    
    def _build_user_prompt(self, texts: List[str]) -> str:
        """ユーザープロンプト生成"""
        import json
        
        segments = [{"id": i, "text": text} for i, text in enumerate(texts)]
        
        return f"""Translate the following segments:

{json.dumps(segments, ensure_ascii=False, indent=2)}

Return ONLY a JSON object in this format:
{{
  "translations": [
    {{"id": 0, "translation": "translated text 0"}},
    {{"id": 1, "translation": "translated text 1"}},
    ...
  ]
}}

IMPORTANT: Return pure JSON without markdown code blocks or extra text."""
    
    def _parse_response(self, response: ChatCompletion, expected_count: int) -> List[str]:
        """レスポンスパース"""
        import json
        
        content = response.choices[0].message.content
        
        # マークダウン除去
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        try:
            data = json.loads(content)
            
            if "translations" not in 
                raise GroqAPIError("Response missing 'translations' field")
            
            translations_list = data["translations"]
            
            if len(translations_list) != expected_count:
                raise GroqAPIError(
                    f"Translation count mismatch: expected {expected_count}, "
                    f"got {len(translations_list)}"
                )
            
            # id順ソート
            translations_list.sort(key=lambda x: x.get("id", 0))
            
            translations = [item.get("translation", "") for item in translations_list]
            
            return translations
            
        except json.JSONDecodeError as e:
            raise GroqAPIError(f"Failed to parse JSON: {e}\nContent: {content[:200]}")
    
    def get_stats(self) -> Dict:
        """統計情報取得（Design原則: 28. データよりも情報を伝える）"""
        cache_stats = translation_cache.get_stats()
        rate_stats = groq_rate_limiter.get_current_usage()
        
        return {
            **self.stats,
            "cache_hit_rate": (
                self.stats["cache_hits"] / 
                (self.stats["cache_hits"] + self.stats["cache_misses"])
                if (self.stats["cache_hits"] + self.stats["cache_misses"]) > 0
                else 0
            ),
            "cache_stats": cache_stats,
            "rate_limit_stats": rate_stats
        }
