"""
Phase Translation v2（リファクタ版）
"""
from pipeline.base_phase import BasePhase, PhaseResult, PhaseError
from pipeline.phase_dependencies import PhaseID
from pipeline.utils.groq_client import GroqClient, GroqAPIError
from pipeline.utils.chunker import SegmentChunker
from app.services.storage import load_job
from config.settings import settings

class TranslationPhase(BasePhase):
    """Groq APIでセグメント一括翻訳 v2"""
    
    def get_phase_name(self) -> str:
        return "Translation"
    
    def get_phase_id(self) -> PhaseID:
        return PhaseID.TRANSLATION
    
    def get_timeout(self) -> int:
        job = load_job(self.job_id)
        segments = job.get("segments", [])
        chunks = SegmentChunker.chunk_segments(segments)
        # チャンク数 × 45秒（API呼び出し + レート制限待機）
        return max(1800, len(chunks) * 45)
    
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
            self.logger.warning("No segments to translate (all flagged)")
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
                "Starting translation",
                src_lang=src_lang,
                tgt_lang=tgt_lang,
                total_segments=len(translatable_segments),
                total_chunks=total_chunks
            )
            
            # チャンクごとに翻訳
            failed_chunks = 0
            
            for i, chunk in enumerate(chunks, 1):
                # セグメント単位の進捗
                completed_segs = sum(len(chunks[j]) for j in range(i - 1))
                self.logger.progress(
                    completed_segs,
                    len(translatable_segments),
                    f"Chunk {i}/{total_chunks}"
                )
                
                texts = [seg["src_text"] for seg in chunk]
                
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
                    
                    failed_chunks += 1
                    
                    # このチャンクのセグメントを失敗マーク
                    for seg in chunk:
                        seg["translation"]["status"] = "failed"
                        seg["translation"]["retries"] += 1
                        # フォールバック：元テキストを暫定的に設定
                        seg["tgt_text"] = seg["src_text"]
                    
                    # 失敗率が50%超えたら中断
                    if failed_chunks / total_chunks > 0.5:
                        raise PhaseError(
                            f"Translation failure rate too high: "
                            f"{failed_chunks}/{total_chunks} chunks failed"
                        )
            
            # 統計情報ログ
            stats = groq.get_stats()
            self.logger.info(
                "Translation completed",
                completed_segments=sum(
                    1 for seg in segments
                    if seg["translation"]["status"] == "completed"
                ),
                failed_segments=sum(
                    1 for seg in segments
                    if seg["translation"]["status"] == "failed"
                ),
                api_requests=stats["total_requests"],
                cache_hit_rate=round(stats["cache_hit_rate"] * 100, 1),
                total_tokens=stats["total_tokens"],
                estimated_cost_usd=round(stats["total_cost_usd"], 4)
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
