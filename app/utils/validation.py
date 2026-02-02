"""
共通バリデーション
Design原則: 6. 一貫性 - ルールを統一
"""
import re
from typing import Optional

from config.settings import settings

class ValidationError(Exception):
    """バリデーションエラー"""
    pass


def validate_youtube_url(url: str) -> tuple[bool, Optional[str]]:
    """
    YouTube URL検証
    Returns: (有効/無効, video_id or None)
    Design原則: 50. ユーザーに厳密さを求めない
    """
    patterns = [
        (r'[?&]v=([^&]+)', 'query'),
        (r'youtu\.be/([^?]+)', 'short'),
        (r'embed/([^?]+)', 'embed')
    ]
    
    for pattern, _ in patterns:
        match = re.search(pattern, url)
        if match:
            video_id = match.group(1)
            # video_idの基本検証（11文字の英数字+記号）
            if re.match(r'^[a-zA-Z0-9_-]{11}$', video_id):
                return True, video_id
    
    return False, None


def validate_language_pair(src_lang: str, tgt_lang: str) -> tuple[bool, Optional[str]]:
    """
    言語ペア検証
    Returns: (有効/無効, エラーメッセージ or None)
    Design原則: 39. 整合性を損なう操作をユーザーに求めない
    """
    # 対応言語チェック
    if src_lang not in settings.SUPPORTED_LANGUAGES:
        return False, f"元言語 '{src_lang}' は対応していません"
    
    if tgt_lang not in settings.SUPPORTED_LANGUAGES:
        return False, f"翻訳先言語 '{tgt_lang}' は対応していません"
    
    # 同一言語チェック
    if src_lang == tgt_lang:
        return False, "元言語と翻訳先言語は異なる必要があります"
    
    return True, None


def validate_job_id(job_id: str) -> bool:
    """
    job_id形式検証（UUID v4）
    Design原則: 13. コンストレイント
    """
    uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
    return bool(re.match(uuid_pattern, job_id, re.IGNORECASE))


def sanitize_filename(filename: str) -> str:
    """
    ファイル名サニタイズ
    Design原則: 15. エラーを回避する - パストラバーサル対策
    """
    # 危険な文字を除去
    safe = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
    # 先頭のドット除去（隠しファイル化を防ぐ）
    safe = safe.lstrip('.')
    # 長さ制限
    return safe[:255]
