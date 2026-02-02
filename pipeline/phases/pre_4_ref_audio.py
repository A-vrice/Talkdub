"""
Phase Pre-4: ref_audio 自動抽出
Design原則: 45. 値を入力させるのではなく結果を選ばせる
"""
import shutil
from pathlib import Path

from pipeline.base_phase import BasePhase, PhaseResult, PhaseError
from app.services.storage import load_job
from pipeline.utils.ffmpeg import extract_audio_segment
from config.settings import settings

class RefAudioPhase(BasePhase):
    """
    話者ごとにref_audio候補を抽出・スコアリング
    
    入力: pre_voice.wav, segments[], speakers[]
    成果物: ref_audio/{speaker_id}_01.wav, speakers[] 更新
    """
    
    def get_phase_name(self) -> str:
        return "Pre-4: RefAudio"
    
    def get_timeout(self) -> int:
        return settings.TIMEOUT_FFMPEG_BASIC * 10  # 話者数×セグメント数
    
    def validate_inputs(self) -> None:
        """入力検証"""
        input_path = self.temp_dir / "pre_voice.wav"
        if not input_path.exists():
            raise PhaseError("pre_voice.wav が見つかりません")
        
        job = load_job(self.job_id)
        if not job.get("segments"):
            raise PhaseError("segments が存在しません")
        if not job.get("speakers"):
            raise PhaseError("speakers が存在しません")
    
    def execute(self) -> PhaseResult:
        """ref_audio抽出実行"""
        input_path = self.temp_dir / "pre_voice.wav"
        job = load_job(self.job_id)
        segments = job["segments"]
        speakers = job["speakers"]
        
        ref_audio_dir = settings.REF_AUDIO_DIR / self.job_id
        ref_audio_dir.mkdir(parents=True, exist_ok=True)
        
        output_files = {}
        
        try:
            for speaker in speakers:
                speaker_id = speaker["speaker_id"]
                
                # この話者のセグメントを抽出
                speaker_segments = [
                    seg for seg in segments
                    if seg["speaker_id"] == speaker_id
                ]
                
                if not speaker_segments:
                    self.logger.warning(f"Speaker {speaker_id} has no segments")
                    continue
                
                # スコアリング
                scored = []
                for seg in speaker_segments:
                    score = self._score_ref_candidate(seg, job)
                    scored.append((score, seg))
                
                # 上位3候補を選択
                scored.sort(reverse=True, key=lambda x: x[0])
                top_candidates = scored[:3]
                
                # スコアが20.0未満なら不採用
                valid_candidates = [
                    (score, seg) for score, seg in top_candidates
                    if score >= 20.0
                ]
                
                if not valid_candidates:
                    self.logger.warning(
                        f"Speaker {speaker_id}: No valid ref_audio candidates "
                        f"(best score: {scored[0][0]:.2f})"
                    )
                    speaker["fallback_mode"] = "preset_voice"
                    speaker["ref_quality_score"] = scored[0][0] if scored else 0.0
                    continue
                
                # 最上位候補を抽出
                best_score, best_seg = valid_candidates[0]
                
                ref_wav_path = ref_audio_dir / f"{speaker_id}_01.wav"
                
                extract_audio_segment(
                    input_path=input_path,
                    output_path=ref_wav_path,
                    start_sec=best_seg["start"],
                    duration_sec=best_seg["end"] - best_seg["start"]
                )
                
                speaker["ref_audio_wav"] = str(ref_wav_path)
                speaker["ref_text"] = best_seg["src_text"]
                speaker["ref_text_lang"] = job["languages"]["src_lang"]
                speaker["ref_quality_score"] = best_score
                
                output_files[speaker_id] = ref_wav_path
                
                self.logger.info(
                    f"Speaker {speaker_id}: ref_audio extracted "
                    f"(score={best_score:.2f}, duration={best_seg['end']-best_seg['start']:.2f}s)"
                )
            
            return PhaseResult(
                success=True,
                output_files=output_files,
                metadata={"speakers": speakers}
            )
            
        except Exception as e:
            self.logger.error(f"ref_audio extraction failed: {e}")
            raise PhaseError(f"ref_audio抽出に失敗しました: {str(e)}")
    
    def _score_ref_candidate(self, seg: dict, job: dict) -> float:
        """
        ref_audio候補スコアリング
        Design原則: 56. 可能性と確率を区別する - 稀な例を優先しすぎない
        """
        score = 100.0
        
        # 1. 長さ（3.0〜8.0秒が最適）
        duration = seg['end'] - seg['start']
        if duration < 3.0 or duration > 8.0:
            score *= 0.3
        elif 4.0 <= duration <= 7.0:
            score *= 1.2
        
        # 2. VAD speech_ratio
        speech_ratio = seg.get('vad_speech_ratio', 0.0)
        if speech_ratio < 0.5:
            score *= 0.1
        elif speech_ratio > 0.85:
            score *= 1.3
        
        # 3. Whisper no_speech_prob
        no_speech = seg.get('whisper', {}).get('no_speech_prob', 1.0)
        if no_speech > 0.5:
            score *= 0.2
        
        # 4. テキスト長
        text_len = len(seg['src_text'])
        if text_len < 8:
            score *= 0.5
        elif text_len > 20:
            score *= 1.1
        
        # 5. 他話者混入チェック
        segments = job['segments']
        for other_seg in segments:
            if other_seg['speaker_id'] != seg['speaker_id']:
                if (abs(other_seg['start'] - seg['end']) < 0.5 or
                    abs(other_seg['end'] - seg['start']) < 0.5):
                    score *= 0.4
                    break
        
        # 6. suspected_hallucination
        if seg['flags'].get('suspected_hallucination'):
            score = 0.0
        
        return score
    
    def validate_outputs(self, result: PhaseResult) -> None:
        """成果物検証"""
        if "speakers" not in result.meta
            raise PhaseError("speakers が更新されていません")
        
        # 少なくとも1話者はref_audioが存在するか
        speakers = result.metadata["speakers"]
        has_ref = any(s.get("ref_audio_wav") for s in speakers)
        
        if not has_ref:
            self.logger.warning("No valid ref_audio found for any speaker (will use preset voices)")

def phase_ref_audio(job_id: str) -> None:
    """Phase Pre-4 実行"""
    phase = RefAudioPhase(job_id)
    result = phase.run()
    
    if not result.success:
        raise PhaseError(result.error)
