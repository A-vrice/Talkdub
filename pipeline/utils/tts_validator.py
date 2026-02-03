"""
TTS生成音声品質検証
Design原則: 15. エラーを回避する
"""
import torchaudio
import torch
import logging
from pathlib import Path
from typing import Tuple

logger = logging.getLogger(__name__)

class TTSValidator:
    """
    TTS生成音声の品質検証
    Design原則: 55. エラー表示は建設的にする
    """
    
    @staticmethod
    def validate(
        audio_path: Path,
        expected_duration_range: Tuple[float, float],
        min_rms_threshold: float = 0.001
    ) -> Tuple[bool, str]:
        """
        生成音声の品質検証
        
        Args:
            audio_path: 検証するwavファイルパス
            expected_duration_range: 期待される長さの範囲（秒）
            min_rms_threshold: 最小RMS閾値（無音検出用）
        
        Returns:
            (合否, エラーメッセージ or "")
        """
        try:
            # ファイル存在チェック
            if not audio_path.exists():
                return False, f"Audio file not found: {audio_path}"
            
            # ファイルサイズチェック（最低10KB）
            file_size = audio_path.stat().st_size
            if file_size < 10 * 1024:
                return False, f"Audio file too small: {file_size} bytes"
            
            # 音声読み込み
            waveform, sample_rate = torchaudio.load(str(audio_path))
            
            # 長さチェック
            duration = waveform.shape[1] / sample_rate
            min_dur, max_dur = expected_duration_range
            
            if duration < min_dur:
                return False, f"Audio too short: {duration:.2f}s < {min_dur:.2f}s"
            
            if duration > max_dur:
                return False, f"Audio too long: {duration:.2f}s > {max_dur:.2f}s"
            
            # 無音チェック（RMS）
            rms = torch.sqrt(torch.mean(waveform ** 2))
            
            if rms < min_rms_threshold:
                return False, f"Audio appears silent: RMS={rms:.6f}"
            
            # クリッピング検出（振幅が0.99超の割合）
            clipping_ratio = (torch.abs(waveform) > 0.99).float().mean().item()
            
            if clipping_ratio > 0.01:  # 1%超
                logger.warning(f"Audio clipping detected: {clipping_ratio:.2%}")
            
            return True, ""
            
        except Exception as e:
            return False, f"Validation failed: {str(e)}"
