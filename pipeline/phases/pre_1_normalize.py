"""
Phase Pre-1: 音声正規化（リファクタ版）
"""
import subprocess
from pathlib import Path

from pipeline.base_phase import BasePhase, PhaseResult, PhaseError
from config.settings import settings

class NormalizePhase(BasePhase):
    
    def get_phase_name(self) -> str:
        return "Pre-1: Normalize"
    
    def get_timeout(self) -> int:
        return settings.TIMEOUT_NORMALIZE
    
    def validate_inputs(self) -> None:
        """入力検証: original.wav が存在するか"""
        input_path = self.temp_dir / "original.wav"
        if not input_path.exists():
            raise PhaseError("original.wav が見つかりません")
    
    def execute(self) -> PhaseResult:
        """音声正規化実行"""
        input_path = self.temp_dir / "original.wav"
        output_path = self.temp_dir / "normalized.wav"
        
        # ffmpeg で正規化
        cmd = [
            "ffmpeg", "-i", str(input_path),
            "-af", "loudnorm=I=-23:TP=-2:LRA=7,aresample=16000",
            "-ac", "1",
            "-ar", "16000",
            "-y",
            str(output_path)
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.get_timeout()
            )
            
            if result.returncode != 0:
                raise PhaseError(f"ffmpeg normalization failed: {result.stderr}")
            
            # 元ファイル削除（ディスク節約）
            input_path.unlink()
            self.logger.debug("Deleted original.wav to save disk space")
            
            return PhaseResult(
                success=True,
                output_files={"normalized": output_path},
                metadata={}
            )
            
        except subprocess.TimeoutExpired:
            raise PhaseError("正規化がタイムアウトしました")
    
    def validate_outputs(self, result: PhaseResult) -> None:
        """成果物検証"""
        if "normalized" not in result.output_files:
            raise PhaseError("normalized.wav が生成されていません")
        
        normalized = result.output_files["normalized"]
        if not normalized.exists():
            raise PhaseError(f"ファイルが存在しません: {normalized}")

def phase_normalize(job_id: str) -> None:
    """Phase Pre-1 実行"""
    phase = NormalizePhase(job_id)
    result = phase.run()
    
    if not result.success:
        raise PhaseError(result.error)
