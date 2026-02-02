"""
セグメントチャンク分割
Design原則: 17. ヒックの法則 - 選択肢を増やしすぎない
"""
from typing import List

from config.settings import settings

class SegmentChunker:
    """
    セグメントをチャンクに分割
    Design原則: 14. プリコンピュテーション - 最適値のプリセット
    """
    
    @staticmethod
    def chunk_segments(
        segments: list[dict],
        char_limit: int = None,
        seg_limit: int = None
    ) -> List[List[dict]]:
        """
        セグメントをチャンクに分割
        
        Args:
            segments: 分割するセグメントリスト
            char_limit: 1チャンクあたりの最大文字数
            seg_limit: 1チャンクあたりの最大セグメント数
        
        Returns:
            チャンクリスト（各チャンクはセグメントのリスト）
        """
        char_limit = char_limit or settings.CHUNK_CHAR_LIMIT_SRC
        seg_limit = seg_limit or settings.CHUNK_SEG_LIMIT
        
        chunks = []
        current_chunk = []
        current_chars = 0
        
        for seg in segments:
            text = seg.get("src_text", "")
            text_len = len(text)
            
            # チャンクの制限チェック
            would_exceed_chars = current_chars + text_len > char_limit
            would_exceed_segs = len(current_chunk) >= seg_limit
            
            if current_chunk and (would_exceed_chars or would_exceed_segs):
                # 現在のチャンクを確定して新規チャンク開始
                chunks.append(current_chunk)
                current_chunk = []
                current_chars = 0
            
            current_chunk.append(seg)
            current_chars += text_len
        
        # 最後のチャンク
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
    
    @staticmethod
    def estimate_total_chars(segments: list[dict]) -> int:
        """セグメントの合計文字数推定"""
        return sum(len(seg.get("src_text", "")) for seg in segments)
