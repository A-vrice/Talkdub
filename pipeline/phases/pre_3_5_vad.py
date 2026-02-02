"""
Phase Pre-3.5: Silero VAD 詳細解析
Design原則: 2. 簡単にする - 負荷を減らす
"""
import torch
from pathlib import Path

from pipeline.base_phase import BasePhase, PhaseResult, PhaseError
from app.services.storage import load_job
from config.settings import settings

class VADPhase(BasePhase):
    """
    Silero VADで各セグメントの音声割合を計算
    
    入力: pre_voice.wav, segments[]
    成果物: segments[].vad_speech_ratio 更新
    """
    
    def get_phase_name(self) -> str:
        return "Pre-3.5: VAD"
    
    def get_timeout(self) -> int:
        return settings.TIMEOUT_VAD
    
    def validate_inputs(self) -> None:
        """入力検証"""
        input_path = self.temp_dir / "pre_voice.wav"
        if not input_path.exists():
            raise PhaseError("pre_voice.wav が見つかりません")
        
        job = load_job(self.job_id)
        if not job.get("segments"):
            raise PhaseError("segments が存在しません（Phase Pre-3を先に実行してください）")
    
    def execute(self) -> PhaseResult:
        """Silero VAD実行"""
        import torchaudio
        
        input_path = self.temp_dir / "pre_voice.wav"
        job = load_job(self.job_id)
        segments = job["segments"]
        
        try:
            # Silero VADモデルロード
            model, utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False,
                onnx=False
            )
            
            get_speech_timestamps = utils[0]
            
            # 音声読み込み（16kHz）
            waveform, sample_rate = torchaudio.load(str(input_path))
            
            if sample_rate != 16000:
                resampler = torchaudio.transforms.Resample(sample_rate, 16000)
                waveform = resampler(waveform)
                sample_rate = 16000
            
            # モノラル化
            if waveform.shape[0] > 1:
                waveform = waveform.mean(dim=0, keepdim=True)
            
            waveform = waveform.squeeze(0)
            
            self.logger.info(f"Running VAD on {len(segments)} segments")
            
            # 全体のVADタイムスタンプ取得
            speech_timestamps = get_speech_timestamps(
                waveform,
                model,
                threshold=0.5,
                sampling_rate=sample_rate
            )
            
            # 各セグメントに対してspeech_ratioを計算
            for seg in segments:
                seg_start_sample = int(seg['start'] * sample_rate)
                seg_end_sample = int(seg['end'] * sample_rate)
                seg_duration = seg['end'] - seg['start']
                
                if seg_duration <= 0:
                    seg['vad_speech_ratio'] = 0.0
                    continue
                
                # そのセグメント範囲内にある speech_timestamps を集計
                speech_duration_samples = 0
                
                for ts in speech_timestamps:
                    overlap_start = max(ts['start'], seg_start_sample)
                    overlap_end = min(ts['end'], seg_end_sample)
                    
                    if overlap_start < overlap_end:
                        speech_duration_samples += (overlap_end - overlap_start)
                
                speech_duration_sec = speech_duration_samples / sample_rate
                seg['vad_speech_ratio'] = min(speech_duration_sec / seg_duration, 1.0)
            
            self.logger.info("VAD analysis completed")
            
            return PhaseResult(
                success=True,
                output_files={},
                metadata={"segments": segments}
            )
            
        except Exception as e:
            self.logger.error(f"VAD execution failed: {e}")
            raise PhaseError(f"VAD解析に失敗しました: {str(e)}")
    
    def validate_outputs(self, result: PhaseResult) -> None:
        """成果物検証"""
        if "segments" not in result.meta
            raise PhaseError("segments が更新されていません")
        
        segments = result.metadata["segments"]
        
        # 全セグメントに vad_speech_ratio が設定されているか
        for seg in segments[:5]:  # サンプルチェック
            if seg.get('vad_speech_ratio') is None:
                raise PhaseError(f"セグメント {seg['seg_id']} に vad_speech_ratio が設定されていません")

def phase_vad(job_id: str) -> None:
    """Phase Pre-3.5 実行"""
    phase = VADPhase(job_id)
    result = phase.run()
    
    if not result.success:
        raise PhaseError(result.error)
