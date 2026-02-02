"""
Phase Pre-2: BGM分離（Demucs）
Design原則: 14. プリコンピュテーション - 最適値のプリセット
"""
import subprocess
import shutil
from pathlib import Path

from pipeline.base_phase import BasePhase, PhaseResult, PhaseError
from config.settings import settings

class SeparatePhase(BasePhase):
    """
    Demucsで音声とBGMを分離
    
    入力: normalized.wav
    成果物: 
    - pre_voice.wav (音声のみ)
    - pre_bgm.wav (BGMのみ)
    """
    
    def get_phase_name(self) -> str:
        return "Pre-2: Separate"
    
    def get_timeout(self) -> int:
        return settings.TIMEOUT_SEPARATE
    
    def validate_inputs(self) -> None:
        """入力検証"""
        input_path = self.temp_dir / "normalized.wav"
        if not input_path.exists():
            raise PhaseError("normalized.wav が見つかりません")
    
    def execute(self) -> PhaseResult:
        """Demucs実行"""
        input_path = self.temp_dir / "normalized.wav"
        
        # Demucs出力ディレクトリ
        demucs_output = self.temp_dir / "demucs_output"
        demucs_output.mkdir(exist_ok=True)
        
        try:
            # Demucs実行（mdx_extra_qモデル使用、CPU専用）
            # Design原則: 42. よいデフォルト - mdx_extra_qは品質優先
            cmd = [
                "demucs",
                "--two-stems=vocals",  # vocalsとinstrumentalのみ分離
                "--device", "cpu",
                "--out", str(demucs_output),
                "--mp3",  # 中間ファイルはmp3で節約
                str(input_path)
            ]
            
            self.logger.info("Starting Demucs separation (CPU mode, this may take 1-2 hours)")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.get_timeout()
            )
            
            if result.returncode != 0:
                raise PhaseError(f"Demucs failed: {result.stderr}")
            
            # Demucsの出力を適切な名前に変更
            # demucs_output/mdx_extra_q/normalized/vocals.wav
            model_dir = demucs_output / "mdx_extra_q" / "normalized"
            vocals_src = model_dir / "vocals.wav"
            instrumental_src = model_dir / "no_vocals.wav"
            
            if not vocals_src.exists():
                raise PhaseError("Demucs vocals.wav が生成されていません")
            
            # 最終的な配置場所へ移動
            pre_voice = self.temp_dir / "pre_voice.wav"
            pre_bgm = self.temp_dir / "pre_bgm.wav"
            
            shutil.move(str(vocals_src), str(pre_voice))
            
            if instrumental_src.exists():
                shutil.move(str(instrumental_src), str(pre_bgm))
            
            # Demucs一時ディレクトリ削除（ディスク節約）
            shutil.rmtree(demucs_output)
            
            # normalized.wav削除
            input_path.unlink()
            self.logger.debug("Deleted normalized.wav to save disk space")
            
            return PhaseResult(
                success=True,
                output_files={
                    "pre_voice": pre_voice,
                    "pre_bgm": pre_bgm if pre_bgm.exists() else None
                },
                metadata={}
            )
            
        except subprocess.TimeoutExpired:
            raise PhaseError("Demucsがタイムアウトしました（音声が長すぎる可能性）")
        except Exception as e:
            self.logger.error(f"Demucs execution failed: {e}")
            raise PhaseError(f"BGM分離に失敗しました: {str(e)}")
    
    def validate_outputs(self, result: PhaseResult) -> None:
        """成果物検証"""
        if "pre_voice" not in result.output_files:
            raise PhaseError("pre_voice.wav が生成されていません")
        
        pre_voice = result.output_files["pre_voice"]
        if not pre_voice or not pre_voice.exists():
            raise PhaseError(f"ファイルが存在しません: {pre_voice}")
        
        # ファイルサイズチェック（最低100KB）
        if pre_voice.stat().st_size < 100 * 1024:
            raise PhaseError("pre_voice.wav が小さすぎます（分離失敗の可能性）")

def phase_separate(job_id: str) -> None:
    """Phase Pre-2 実行"""
    phase = SeparatePhase(job_id)
    result = phase.run()
    
    if not result.success:
        raise PhaseError(result.error)
