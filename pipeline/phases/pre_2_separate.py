"""
Phase Pre-2: BGM分離（リファクタ版）
"""
import subprocess
import shutil
from pathlib import Path

from pipeline.base_phase import BasePhase, PhaseResult, PhaseError
from pipeline.phase_dependencies import PhaseID
from config.settings import settings

class SeparatePhase(BasePhase):
    """Demucsで音声とBGMを分離"""
    
    def get_phase_name(self) -> str:
        return "Pre-2: Separate"
    
    def get_phase_id(self) -> PhaseID:
        return PhaseID.PRE_2_SEPARATE
    
    def get_timeout(self) -> int:
        return settings.TIMEOUT_SEPARATE
    
    def execute(self) -> PhaseResult:
        """Demucs実行"""
        input_path = self.temp_dir / "normalized.wav"
        demucs_output = self.temp_dir / "demucs_output"
        demucs_output.mkdir(exist_ok=True)
        
        try:
            # Demucs実行
            cmd = [
                "demucs",
                "--two-stems=vocals",
                "--device", "cpu",
                "--out", str(demucs_output),
                str(input_path)
            ]
            
            # Design原則: 65. 進捗を返す
            self.logger.info("Starting Demucs separation (CPU mode, estimated 60-90 min)")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.get_timeout()
            )
            
            if result.returncode != 0:
                raise PhaseError(f"Demucs failed: {result.stderr}")
            
            # 出力ファイル移動
            model_dir = demucs_output / "htdemucs" / "normalized"
            vocals_src = model_dir / "vocals.wav"
            instrumental_src = model_dir / "no_vocals.wav"
            
            if not vocals_src.exists():
                raise PhaseError("Demucs vocals.wav not generated")
            
            pre_voice = self.temp_dir / "pre_voice.wav"
            pre_bgm = self.temp_dir / "pre_bgm.wav"
            
            shutil.move(str(vocals_src), str(pre_voice))
            
            if instrumental_src.exists():
                shutil.move(str(instrumental_src), str(pre_bgm))
            
            # クリーンアップ
            shutil.rmtree(demucs_output)
            input_path.unlink()
            
            self.logger.info("Demucs separation completed")
            
            return PhaseResult(
                success=True,
                output_files={
                    "pre_voice": pre_voice,
                    "pre_bgm": pre_bgm if pre_bgm.exists() else None
                },
                metadata={}
            )
            
        except subprocess.TimeoutExpired:
            raise PhaseError("Demucs timed out")
        except Exception as e:
            raise PhaseError(f"BGM separation failed: {str(e)}")

def phase_separate(job_id: str) -> None:
    """Phase Pre-2 実行"""
    phase = SeparatePhase(job_id)
    result = phase.run()
    
    if not result.success:
        raise PhaseError(result.error)
