"""
Phase Translation: Groq API翻訳
Design原則: 20. メジャーなタスクに最適化する
"""
from pipeline.base_phase import BasePhase, PhaseResult, PhaseError
from pipeline.phase_dependencies import PhaseID
from pipeline.utils.groq_client import GroqClient, GroqAPIError
from pipeline.utils.chunker import SegmentChunker
from app.services.storage import load_job
from config.settings import settings

class TranslationPhase(BasePhase):
    """
    Groq APIでセグメント一括翻訳
    
    入力: segments[], languages
    成果物: segments[].tgt_text 更新
    """
    
    def get_phase_name(self) -> str:
        return "Translation"
    
    def get_phase_id(self) -> PhaseID:
        return PhaseID.TRANSLATION
    
    def get_timeout(self) -> int:
        # チャンク数 × 30秒（API呼び出し想定）
        job = load_job(self.job_id)
        segments = job.get("segments", [])
        chunks = SegmentChunker.chunk_segments(segments)
        return max(1800, len(chunks) * 30)
    
    def execute(self) -> PhaseResult:
        """翻訳実行"""
        job = load_job(self.job_id)
        segments = job["segments"]
        src_lang = job["languages"]["src_lang"]
        tgt_lang = job["languages"]["tgt_lang"]
        
        # ハルシネーションフラグのセグメントはスキップ
        translatable_segments = [
            seg for seg in segments
            if not seg["flags"].get("suspected_hallucination", False)
        ]
        
        if not translatable_segments:
            self.logger.warning("No segments to translate (all flagged as hallucination)")
            return PhaseResult(
                success=True,
                output_files={},
                metadata={"segments": segments}
            )
        
        try:
            # Groqクライアント初期化
            groq = GroqClient()
            
            # チャンク分割
            chunks = SegmentChunker.chunk_segments(translatable_segments)
            total_chunks = len(chunks)
            
            self.logger.info(
                f"Starting translation",
                src_lang=src_lang,
                tgt_lang=tgt_lang,
                total_segments=len(translatable_segments),
                total_chunks=total_chunks
            )
            
            # チャンクごとに翻訳
            for i, chunk in enumerate(chunks, 1):
                self.logger.progress(i, total_chunks, f"Translating chunk {i}/{total_chunks}")
                
                # このチャンクのテキストを抽出
                texts = [seg["src_text"] for seg in chunk]
                
                # Groq API呼び出し
                try:
                    translations = groq.translate(
                        texts=texts,
                        src_lang=src_lang,
                        tgt_lang=tgt_lang,
                        context=job.get("source", {}).get("video_title")
                    )
                    
                    # セグメントに反映
                    for seg, translation in zip(chunk, translations):
                        seg["tgt_text"] = translation
                        seg["translation"]["provider"] = "groq"
                        seg["translation"]["status"] = "completed"
                    
                except GroqAPIError as e:
                    self.logger.error(f"Translation failed for chunk {i}: {e}")
                    
                    # このチャンクのセグメントを失敗マーク
                    for seg in chunk:
                        seg["translation"]["status"] = "failed"
                        seg["translation"]["retries"] += 1
                    
                    # Design原則: 56. 可能性と確率を区別する
                    # 一部失敗は許容して継続
                    if i == total_chunks:  # 最後のチャンクでも失敗したら例外
                        raise PhaseError(f"Translation failed on final chunk: {str(e)}")
            
            # 統計情報
            completed_count = sum(
                1 for seg in segments
                if seg["translation"]["status"] == "completed"
            )
            
            self.logger.info(
                f"Translation completed",
                completed_segments=completed_count,
                total_segments=len(segments),
                success_rate=round(completed_count / len(segments) * 100, 1)
            )
            
            return PhaseResult(
                success=True,
                output_files={},
                metadata={"segments": segments}
            )
            
        except Exception as e:
            raise PhaseError(f"Translation phase failed: {str(e)}")

def phase_translation(job_id: str) -> None:
    """Phase Translation 実行"""
    phase = TranslationPhase(job_id)
    result = phase.run()
    
    if not result.success:
        raise PhaseError(result.error)
