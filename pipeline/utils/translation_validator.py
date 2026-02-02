"""
翻訳品質検証
Design原則: 15. エラーを回避する
"""
import re
import logging
from typing import List, Tuple

from config.settings import settings

logger = logging.getLogger(__name__)

class TranslationValidator:
    """
    翻訳結果の品質検証
    Design原則: 55. エラー表示は建設的にする
    """
    
    @staticmethod
    def validate(
        originals: List[str],
        translations: List[str],
        src_lang: str,
        tgt_lang: str
    ) -> Tuple[bool, List[str]]:
        """
        翻訳品質検証
        
        Returns:
            (全体の合否, 警告メッセージリスト)
        """
        warnings = []
        critical_errors = 0
        
        for i, (orig, trans) in enumerate(zip(originals, translations)):
            # 1. 空文字チェック
            if not trans or not trans.strip():
                warnings.append(f"[CRITICAL] Segment {i}: Empty translation")
                critical_errors += 1
                continue
            
            # 2. 長さ比率チェック
            length_ratio = len(trans) / len(orig) if len(orig) > 0 else 0
            
            if length_ratio < settings.TRANSLATION_MIN_LENGTH_RATIO:
                warnings.append(
                    f"[WARNING] Segment {i}: Translation too short "
                    f"(ratio={length_ratio:.2f})"
                )
            elif length_ratio > settings.TRANSLATION_MAX_LENGTH_RATIO:
                warnings.append(
                    f"[WARNING] Segment {i}: Translation too long "
                    f"(ratio={length_ratio:.2f})"
                )
            
            # 3. 元言語混入チェック（日本語→英語の場合）
            if src_lang == "ja" and tgt_lang == "en":
                if re.search(r'[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff]', trans):
                    warnings.append(
                        f"[WARNING] Segment {i}: Japanese characters remain in English translation"
                    )
            
            # 4. 記号のみチェック
            if re.match(r'^[\s\W]+$', trans):
                warnings.append(
                    f"[WARNING] Segment {i}: Translation contains only symbols/whitespace"
                )
            
            # 5. 元テキストと完全一致（翻訳されていない可能性）
            if orig.strip() == trans.strip():
                warnings.append(
                    f"[INFO] Segment {i}: Translation identical to original (may be intentional)"
                )
        
        # クリティカルエラーが全体の10%超えたら失敗
        is_valid = critical_errors < len(originals) * 0.1
        
        return is_valid, warnings
