"""
Groq API クライアント
Design原則: 18. 複雑性をシステム側へ
"""
import time
import logging
from typing import Optional, Any
from groq import Groq
from groq.types.chat import ChatCompletion

from config.settings import settings

logger = logging.getLogger(__name__)

class GroqAPIError(Exception):
    """Groq API エラー"""
    pass

class GroqClient:
    """
    Groq APIラッパー
    Design原則: 15. エラーを回避する - リトライ機能内蔵
    """
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.GROQ_API_KEY
        if not self.api_key:
            raise GroqAPIError("GROQ_API_KEY not set")
        
        self.client = Groq(api_key=self.api_key)
        self.model = "llama-3.3-70b-versatile"  # 2026年2月時点の最新モデル
    
    def translate(
        self,
        texts: list[str],
        src_lang: str,
        tgt_lang: str,
        context: Optional[str] = None,
        max_retries: int = None
    ) -> list[str]:
        """
        テキスト一括翻訳
        
        Args:
            texts: 翻訳するテキストリスト
            src_lang: 元言語コード
            tgt_lang: 翻訳先言語コード
            context: コンテキスト（動画のタイトル等）
            max_retries: 最大リトライ回数
        
        Returns:
            翻訳済みテキストリスト
        """
        max_retries = max_retries or settings.MAX_RETRIES
        
        # システムプロンプト
        system_prompt = self._build_system_prompt(src_lang, tgt_lang, context)
        
        # ユーザープロンプト（JSON形式で要求）
        user_prompt = self._build_user_prompt(texts)
        
        # リトライループ
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.3,  # 一貫性重視
                    max_tokens=4096,
                    response_format={"type": "json_object"}  # JSON強制
                )
                
                # レスポンスパース
                translations = self._parse_response(response, len(texts))
                
                # バリデーション
                self._validate_translations(texts, translations)
                
                return translations
                
            except Exception as e:
                logger.warning(f"Groq API call failed (attempt {attempt + 1}/{max_retries}): {e}")
                
                if attempt < max_retries - 1:
                    # 指数バックオフ
                    delay = settings.BACKOFF_BASE_SEC * (2 ** attempt)
                    time.sleep(delay)
                else:
                    raise GroqAPIError(f"Translation failed after {max_retries} attempts: {str(e)}")
    
    def translate_shortened(
        self,
        text: str,
        src_lang: str,
        tgt_lang: str,
        max_length: int,
        max_retries: int = None
    ) -> str:
        """
        短縮翻訳（Post処理の例外対応用）
        
        Args:
            text: 翻訳するテキスト
            src_lang: 元言語コード
            tgt_lang: 翻訳先言語コード
            max_length: 最大文字数
            max_retries: 最大リトライ回数
        
        Returns:
            短縮翻訳済みテキスト
        """
        max_retries = max_retries or settings.MAX_RETRIES
        
        system_prompt = f"""You are a professional translator specialized in concise translation.
Translate the following text from {src_lang} to {tgt_lang}.
IMPORTANT: The translation must be {max_length} characters or less while preserving the core meaning.
Prioritize brevity over completeness."""
        
        user_prompt = f"""Text to translate: "{text}"

Return ONLY a JSON object in this format:
{{"translation": "your concise translation here"}}"""
        
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.5,
                    max_tokens=512,
                    response_format={"type": "json_object"}
                )
                
                import json
                result = json.loads(response.choices[0].message.content)
                translation = result.get("translation", "")
                
                if not translation:
                    raise GroqAPIError("Empty translation received")
                
                if len(translation) > max_length:
                    raise GroqAPIError(f"Translation too long: {len(translation)} > {max_length}")
                
                return translation
                
            except Exception as e:
                logger.warning(f"Shortened translation failed (attempt {attempt + 1}/{max_retries}): {e}")
                
                if attempt < max_retries - 1:
                    delay = settings.BACKOFF_BASE_SEC * (2 ** attempt)
                    time.sleep(delay)
                else:
                    raise GroqAPIError(f"Shortened translation failed: {str(e)}")
    
    def _build_system_prompt(self, src_lang: str, tgt_lang: str, context: Optional[str]) -> str:
        """システムプロンプト生成"""
        lang_names = {
            "ja": "Japanese", "zh": "Chinese", "en": "English",
            "de": "German", "fr": "French", "it": "Italian",
            "es": "Spanish", "pt": "Portuguese", "ru": "Russian", "ko": "Korean"
        }
        
        src_name = lang_names.get(src_lang, src_lang)
        tgt_name = lang_names.get(tgt_lang, tgt_lang)
        
        prompt = f"""You are a professional translator specialized in video subtitle translation.
Translate the following segments from {src_name} to {tgt_name}.

IMPORTANT RULES:
1. Preserve the meaning and tone (formal/casual) of the original text
2. Keep translations natural and concise for spoken dialogue
3. Maintain consistency in terminology throughout
4. DO NOT add explanations, notes, or extra content
5. If a segment is a sound effect (like [laugh], [music]), keep it as-is or translate appropriately"""
        
        if context:
            prompt += f"\n6. Context: This is from a video about '{context}'"
        
        return prompt
    
    def _build_user_prompt(self, texts: list[str]) -> str:
        """ユーザープロンプト生成"""
        import json
        
        segments = [{"id": i, "text": text} for i, text in enumerate(texts)]
        
        prompt = f"""Translate the following segments:

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
        
        return prompt
    
    def _parse_response(self, response: ChatCompletion, expected_count: int) -> list[str]:
        """レスポンスパース"""
        import json
        
        content = response.choices[0].message.content
        
        try:
            # マークダウンコードブロック除去（念のため）
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            data = json.loads(content)
            
            if "translations" not in 
                raise GroqAPIError("Response missing 'translations' field")
            
            translations_list = data["translations"]
            
            if len(translations_list) != expected_count:
                raise GroqAPIError(
                    f"Translation count mismatch: expected {expected_count}, got {len(translations_list)}"
                )
            
            # id順にソート
            translations_list.sort(key=lambda x: x.get("id", 0))
            
            # translation フィールドを抽出
            translations = [item.get("translation", "") for item in translations_list]
            
            return translations
            
        except json.JSONDecodeError as e:
            raise GroqAPIError(f"Failed to parse JSON response: {e}\nContent: {content}")
    
    def _validate_translations(self, originals: list[str], translations: list[str]) -> None:
        """翻訳結果バリデーション"""
        if len(originals) != len(translations):
            raise GroqAPIError("Translation count mismatch after parsing")
        
        for i, (orig, trans) in enumerate(zip(originals, translations)):
            # 空文字チェック
            if not trans or not trans.strip():
                raise GroqAPIError(f"Empty translation at index {i}")
            
            # 極端に短い/長い翻訳（元の1/10または5倍超）
            if len(trans) < len(orig) / 10 or len(trans) > len(orig) * 5:
                logger.warning(
                    f"Translation length suspicious at index {i}: "
                    f"orig={len(orig)}, trans={len(trans)}"
                )
