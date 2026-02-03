"""
Phase TTS: Qwen3-TTS 音声合成
Design原則: 20. メジャーなタスクに最適化する
"""
from pathlib import Path
import time

from pipeline.base_phase import BasePhase, PhaseResult, PhaseError
from pipeline.phase_dependencies import PhaseID
from pipeline.utils.qwen_tts_client import QwenTTSClient, QwenTTSError
from pipeline.utils.tts_validator import TTSValidator
from app.services.storage import load_job
from config.settings import settings

class TTSPhase(BasePhase):
    """
    Qwen3-TTS でセグメント音声合成
    
    入力: segments[], speakers[]
    成果物: tts_output/{seg_id}.wav, segments[].tts.wav_path, segments[].timing.tts_duration
    """
    
    def get_phase_name(self) -> str:
        return "TTS"
    
    def get_phase_id(self) -> PhaseID:
        return PhaseID.TTS
    
    def get_timeout(self) -> int:
        # セグメント数 × 5分（CPU処理想定）
        job = load_job(self.job_id)
        segments = job.get("segments", [])
        processable = [
            seg for seg in segments
            if seg["translation"]["status"] == "completed"
            and not seg["flags"].get("suspected_hallucination", False)
        ]
        return max(3600, len(processable) * settings.TIMEOUT_TTS_PER_SEGMENT)
    
    def execute(self) -> PhaseResult:
        """TTS実行"""
        job = load_job(self.job_id)
        segments = job["segments"]
        speakers = job["speakers"]
        tgt_lang = job["languages"]["tgt_lang"]
        
        # 処理対象セグメント（翻訳完了 & 非ハルシネーション）
        processable_segments = [
            seg for seg in segments
            if seg["translation"]["status"] == "completed"
            and not seg["flags"].get("suspected_hallucination", False)
        ]
        
        if not processable_segments:
            self.logger.warning("No segments to synthesize")
            return PhaseResult(
                success=True,
                output_files={},
                metadata={"segments": segments}
            )
        
        # 出力ディレクトリ作成
        tts_output_dir = settings.OUTPUT_DIR / self.job_id / "tts_output"
        tts_output_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Qwen3-TTSクライアント初期化
            tts_client = QwenTTSClient()
            
            total_segs = len(processable_segments)
            success_count = 0
            failed_count = 0
            
            self.logger.info(
                "Starting TTS synthesis",
                total_segments=total_segs,
                tgt_lang=tgt_lang
            )
            
            # 話者ごとにref_audio情報を取得
            speaker_ref_map = {
                spk["speaker_id"]: {
                    "ref_audio_path": Path(spk["ref_audio_wav"]) if spk.get("ref_audio_wav") else None,
                    "ref_text": spk.get("ref_text"),
                    "fallback_mode": spk.get("fallback_mode", "normal")
                }
                for spk in speakers
            }
            
            # セグメント逐次処理（CPU負荷考慮）
            for i, seg in enumerate(processable_segments, 1):
                self.logger.progress(i, total_segs, f"Synthesizing segment {i}/{total_segs}")
                
                seg_id = seg["seg_id"]
                text = seg["tgt_text"]
                speaker_id = seg["speaker_id"]
                
                # 出力パス
                output_path = tts_output_dir / f"{seg_id}.wav"
                
                # 話者のref_audio情報取得
                speaker_ref = speaker_ref_map.get(speaker_id, {})
                ref_audio_path = speaker_ref.get("ref_audio_path")
                ref_text = speaker_ref.get("ref_text")
                
                # フォールバックモードチェック
                if speaker_ref.get("fallback_mode") == "preset_voice":
                    self.logger.warning(
                        f"Using preset voice for speaker {speaker_id} (no valid ref_audio)"
                    )
                    ref_audio_path = None
                    ref_text = None
                
                try:
                    # TTS合成
                    start_time = time.time()
                    
                    duration = tts_client.synthesize(
                        text=text,
                        ref_audio_path=ref_audio_path,
                        ref_text=ref_text,
                        language=tgt_lang,
                        output_path=output_path
                    )
                    
                    synthesis_time = time.time() - start_time
                    
                    # 品質検証
                    # 期待される長さ：元セグメント長の0.5〜2.5倍
                    orig_duration = seg["end"] - seg["start"]
                    expected_range = (orig_duration * 0.5, orig_duration * 2.5)
                    
                    is_valid, error_msg = TTSValidator.validate(
                        audio_path=output_path,
                        expected_duration_range=expected_range
                    )
                    
                    if not is_valid:
                        raise QwenTTSError(f"Quality validation failed: {error_msg}")
                    
                    # セグメントに反映
                    seg["tts"]["wav_path"] = str(output_path)
                    seg["tts"]["status"] = "completed"
                    seg["timing"]["tts_duration"] = duration
                    
                    success_count += 1
                    
                    # RTF（Real-Time Factor）計算
                    rtf = synthesis_time / duration if duration > 0 else 0
                    
                    self.logger.debug(
                        f"Segment {seg_id} synthesized",
                        duration=round(duration, 2),
                        synthesis_time=round(synthesis_time, 2),
                        rtf=round(rtf, 2)
                    )
                    
                except QwenTTSError as e:
                    self.logger.error(f"TTS failed for segment {seg_id}: {e}")
                    
                    failed_count += 1
                    seg["tts"]["status"] = "failed"
                    seg["tts"]["retries"] += 1
                    
                    # 失敗率が50%超えたら中断
                    if failed_count / total_segs > 0.5:
                        raise PhaseError(
                            f"TTS failure rate too high: "
                            f"{failed_count}/{total_segs} segments failed"
                        )
            
            # モデルをメモリから解放
            tts_client.unload_model()
            
            self.logger.info(
                "TTS synthesis completed",
                success_count=success_count,
                failed_count=failed_count,
                success_rate=round(success_count / total_segs * 100, 1)
            )
            
            return PhaseResult(
                success=True,
                output_files={"tts_output_dir": tts_output_dir},
                metadata={"segments": segments}
            )
            
        except Exception as e:
            # エラー時もモデル解放
            try:
                tts_client.unload_model()
            except:
                pass
            
            raise PhaseError(f"TTS phase failed: {str(e)}")

def phase_tts(job_id: str) -> None:
    """Phase TTS 実行"""
    phase = TTSPhase(job_id)
    result = phase.run()
    
    if not result.success:
        raise PhaseError(result.error)
