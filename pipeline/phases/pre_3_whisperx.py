"""
Phase Pre-3: WhisperX（リファクタ版）
"""
import whisperx
import torch
import gc

from pipeline.base_phase import BasePhase, PhaseResult, PhaseError
from pipeline.phase_dependencies import PhaseID
from app.services.storage import load_job
from config.settings import settings

class WhisperXPhase(BasePhase):
    """WhisperXで音声認識 + 話者分離"""
    
    def get_phase_name(self) -> str:
        return "Pre-3: WhisperX"
    
    def get_phase_id(self) -> PhaseID:
        return PhaseID.PRE_3_WHISPERX
    
    def get_timeout(self) -> int:
        return settings.TIMEOUT_WHISPERX
    
    def execute(self) -> PhaseResult:
        """WhisperX実行"""
        input_path = self.temp_dir / "pre_voice.wav"
        job = load_job(self.job_id)
        src_lang = job["languages"]["src_lang"]
        
        device = "cpu"
        compute_type = "float32"
        
        try:
            # Step 1: ASR
            self.logger.info(f"Loading WhisperX model (lang={src_lang})")
            
            model = whisperx.load_model(
                "large-v2",
                device=device,
                compute_type=compute_type,
                language=src_lang
            )
            
            audio = whisperx.load_audio(str(input_path))
            result = model.transcribe(audio, language=src_lang)
            
            self.logger.progress(1, 3, "Transcription completed")
            
            # モデル解放（メモリ節約）
            del model
            gc.collect()
            
            # Step 2: Alignment
            self.logger.info("Loading alignment model")
            
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
            
            self.logger.progress(2, 3, "Alignment completed")
            
            # モデル解放
            del model_a
            gc.collect()
            
            # Step 3: Diarization
            if not settings.HF_TOKEN:
                self.logger.warning("HF_TOKEN not set, skipping diarization")
                diarize_segments = result["segments"]
            else:
                self.logger.info("Loading diarization model")
                
                diarize_model = whisperx.DiarizationPipeline(
                    use_auth_token=settings.HF_TOKEN,
                    device=device
                )
                
                diarize_segments_obj = diarize_model(audio)
                result = whisperx.assign_word_speakers(diarize_segments_obj, result)
                diarize_segments = result["segments"]
                
                # モデル解放
                del diarize_model
                gc.collect()
            
            self.logger.progress(3, 3, "Diarization completed")
            
            # セグメント変換
            segments = self._convert_segments(diarize_segments)
            speakers = self._extract_speakers(segments)
            
            self.logger.info(
                f"WhisperX completed",
                total_segments=len(segments),
                unique_speakers=len(speakers)
            )
            
            return PhaseResult(
                success=True,
                output_files={},
                metadata={
                    "segments": segments,
                    "speakers": speakers
                }
            )
            
        except Exception as e:
            raise PhaseError(f"WhisperX failed: {str(e)}")
    
    def _convert_segments(self, whisperx_segments: list) -> list:
        """WhisperXセグメントをjob.json形式に変換"""
        segments = []
        
        for i, seg in enumerate(whisperx_segments):
            segment = {
                "seg_id": f"seg_{i:04d}",
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
                
                "vad_speech_ratio": None,
                
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

def phase_whisperx(job_id: str) -> None:
    """Phase Pre-3 実行"""
    phase = WhisperXPhase(job_id)
    result = phase.run()
    
    if not result.success:
        raise PhaseError(result.error)
