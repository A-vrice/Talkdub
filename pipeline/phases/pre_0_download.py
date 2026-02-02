"""
Phase Pre-0: YouTube動画ダウンロード（リファクタ版）
Design原則: 23. オブジェクトベース
"""
import subprocess
from pathlib import Path

from pipeline.base_phase import BasePhase, PhaseResult, PhaseError
from pipeline.utils.ffmpeg import get_audio_duration
from config.settings import settings

class DownloadPhase(BasePhase):
    
    def get_phase_name(self) -> str:
        return "Pre-0: Download"
    
    def get_timeout(self) -> int:
        return settings.TIMEOUT_DOWNLOAD
    
    def validate_inputs(self) -> None:
        """入力検証: job.json の source.url が存在するか"""
        from app.services.storage import load_job
        job = load_job(self.job_id)
        
        if not job.get("source", {}).get("url"):
            raise PhaseError("source.url が設定されていません")
    
    def execute(self) -> PhaseResult:
        """YouTube動画ダウンロード実行"""
        from app.services.storage import load_job
        job = load_job(self.job_id)
        video_url = job["source"]["url"]
        
        output_path = self.temp_dir / "original.wav"
        
        # yt-dlp実行
        cmd = [
            "yt-dlp",
            "--extract-audio",
            "--audio-format", "wav",
            "--audio-quality", "0",
            "--output", str(output_path.with_suffix('.%(ext)s')),
            "--no-playlist",
            "--no-warnings",
            video_url
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.get_timeout()
            )
            
            if result.returncode != 0:
                raise PhaseError(f"yt-dlp failed: {result.stderr}")
            
            # メタデータ取得
            duration = get_audio_duration(output_path)
            
            return PhaseResult(
                success=True,
                output_files={"original": output_path},
                metadata={"media": {"duration_sec": duration}}
            )
            
        except subprocess.TimeoutExpired:
            raise PhaseError("ダウンロードがタイムアウトしました（動画が長すぎる可能性）")
    
    def validate_outputs(self, result: PhaseResult) -> None:
        """成果物検証"""
        if "original" not in result.output_files:
            raise PhaseError("original.wav が生成されていません")
        
        original = result.output_files["original"]
        if not original.exists():
            raise PhaseError(f"ファイルが存在しません: {original}")
        
        # ファイルサイズチェック（最低1MB）
        if original.stat().st_size < 1024 * 1024:
            raise PhaseError("ダウンロードされた音声ファイルが小さすぎます")

# 関数形式のエントリーポイント（既存コードとの互換性）
def phase_download(job_id: str) -> None:
    """Phase Pre-0 実行（ラッパー）"""
    phase = DownloadPhase(job_id)
    result = phase.run()
    
    if not result.success:
        raise PhaseError(result.error)
