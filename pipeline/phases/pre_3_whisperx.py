"""
Phase Pre-3: WhisperX（ASR + Diarization）
Design原則: 18. 複雑性をシステム側へ
"""
import whisperx
import torch
import json
from pathlib import Path

from pipeline.base_phase import BasePhase, PhaseResult, PhaseError
from app.services.storage import load_job
from config.settings import settings

class WhisperXPhase(BasePhase):
    """
    WhisperXで音声認識 + 話者分離
    
    入力: pre_voice.wav
    成果物: job.json の segments[], speakers[] 更新
    """
    
    def get_phase_name(self) -> str:
        return "Pre-3: WhisperX"
    
    def get_timeout(self) -> int:
        return settings.TIMEOUT_WHISPERX
    
    def validate_inputs(self) -> None:
        """入力検証"""
        input_path = self.temp_dir / "pre_voice.wav"
        if not input_path.exists():
            raise PhaseError("pre_voice.wav が見つかりません")
        
        job = load_job(self.job_id)
        if not job.get("languages", {}).get("src_lang"):
            raise PhaseError("src_lang が設定されていません")
    
    def execute(self) -> PhaseResult:
        """WhisperX実行"""
        input_path = self.temp_dir / "pre_voice.wav"
        job = load_job(self.job_id)
        src_lang = job["languages"]["src_lang"]
        
        try:
            # CPU専用設定
            device = "cpu"
            compute_type = "float32"
            
            self.logger.info(f"Loading WhisperX model (language={src_lang}, device={device})")
            
            # Step 1: ASR (Whisper)
            model = whisperx.load_model(
                "large-v2",
                device=device,
                compute_type=compute_type,
                language=src_lang
            )
            
            audio = whisperx.load_audio(str(input_path))
            result = model.transcribe(audio, language=src_lang)
            
            self.logger.info(f"Transcription completed, {len(result['segments'])} segments")
            
            # Step 2: Alignment（単語レベルのタイムスタンプ）
            model_a, metadata = whisperx.load_align_model(
                language_code=src_lang,
                device=device
            )
            
            result = whisperx.align(
                result["segments"],
                model_a,
                metadata,
                audio,
                device
            )
            
            self.logger.info("Alignment completed")
            
            # Step 3: Diarization（話者分離）
            if not settings.HF_TOKEN:
                self.logger.warning("HF_TOKEN not set, skipping diarization")
                diarize_segments = result["segments"]
            else:
                diarize_model = whisperx.DiarizationPipeline(
                    use_auth_token=settings.HF_TOKEN,
                    device=device
                )
                
                diarize_segments_obj = diarize_model(audio)
                
                # セグメントに話者情報を割り当て
                result = whisperx.assign_word_speakers(
                    diarize_segments_obj,
                    result
                )
                diarize_segments = result["segments"]
            
            self.logger.info(f"Diarization completed, {len(diarize_segments)} segments")
            
            # セグメントをjob.json形式に変換
            segments = self._convert_segments(diarize_segments)
            speakers = self._extract_speakers(segments)
            
            return PhaseResult(
                success=True,
                output_files={},
                metadata={
                    "segments": segments,
                    "speakers": speakers
                }
            )
            
        except Exception as e:
            self.logger.error(f"WhisperX execution failed: {e}")
            raise PhaseError(f"音声認識に失敗しました: {str(e)}")
    
    def _convert_segments(self, whisperx_segments: list) -> list:
        """WhisperXセグメントをjob.json形式に変換"""
        segments = []
        
        for i, seg in enumerate(whisperx_segments):
            seg_id = f"seg_{i:04d}"
            
            segment = {
                "seg_id": seg_id,
                "start": seg["start"],
                "end": seg["end"],
                "src_text": seg["text"].strip(),
                "tgt_text": None,
                "speaker_id": seg.get("speaker", "SPEAKER_00"),
                
                "flags": {
                    "suspected_hallucination": False,
                    "silenced": False,
                    "shortened": False
                },
                
                "whisper": {
                    "no_speech_prob": seg.get("no_speech_prob", 0.0),
                    "avg_logprob": seg.get("avg_logprob", 0.0),
                    "words": seg.get("words", [])
                },
                
                "vad_speech_ratio": None,  # Phase 3.5で設定
                
                "translation": {
                    "provider": None,
                    "retries": 0,
                    "status": "pending"
                },
                
                "tts": {
                    "wav_path": None,
                    "status": "pending",
                    "retries": 0
                },
                
                "timing": {
                    "tts_duration": None,
                    "final_start": None,
                    "final_end": None,
                    "atempo_applied": None,
                    "overlap_applied": 0.0
                }
            }
            
            segments.append(segment)
        
        return segments
    
    def _extract_speakers(self, segments: list) -> list:
        """話者リストを抽出"""
        speaker_ids = set(seg["speaker_id"] for seg in segments)
        
        speakers = []
        for speaker_id in sorted(speaker_ids):
            speakers.append({
                "speaker_id": speaker_id,
                "ref_audio_wav": None,
                "ref_text": None,
                "ref_text_lang": None,
                "fallback_mode": "normal",
                "ref_quality_score": None
            })
        
        return speakers
    
    def validate_outputs(self, result: PhaseResult) -> None:
        """成果物検証"""
        if "segments" not in result.meta
            raise PhaseError("segments が生成されていません")
        
        segments = result.metadata["segments"]
        if len(segments) == 0:
            raise PhaseError("セグメントが1つも検出されませんでした（無音の可能性）")
        
        # 最低限のフィールドチェック
        required_fields = ["seg_id", "start", "end", "src_text", "speaker_id"]
        for seg in segments[:3]:  # 最初の3つをサンプルチェック
            for field in required_fields:
                if field not in seg:
                    raise PhaseError(f"セグメントに必須フィールド '{field}' がありません")

def phase_whisperx(job_id: str) -> None:
    """Phase Pre-3 実行"""
    phase = WhisperXPhase(job_id)
    result = phase.run()
    
    if not result.success:
        raise PhaseError(result.error)
