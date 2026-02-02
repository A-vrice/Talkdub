"""
Phase依存関係管理
Design原則: 32. 前提条件は先に提示する
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from enum import Enum

class PhaseID(Enum):
    """Phase識別子（順序保証）"""
    PRE_0_DOWNLOAD = "pre_0"
    PRE_1_NORMALIZE = "pre_1"
    PRE_2_SEPARATE = "pre_2"
    PRE_3_WHISPERX = "pre_3"
    PRE_3_5_VAD = "pre_3.5"
    PRE_4_REF_AUDIO = "pre_4"
    PRE_5_HALLUCINATION = "pre_5"
    TRANSLATION = "translation"
    TTS = "tts"
    POST_1_TIMELINE = "post_1"
    POST_2_MIX = "post_2"
    POST_3_FINALIZE = "post_3"
    POST_4_MANIFEST = "post_4"

@dataclass
class PhaseDependency:
    """Phase依存情報"""
    phase_id: PhaseID
    required_files: list[str]  # temp/{job_id}/以下の必須ファイル
    required_job_fields: list[str]  # job.jsonの必須フィールド（ドット記法）
    required_env_vars: list[str]  # 必須環境変数
    estimated_duration_min: float  # 推定実行時間（30分動画基準）

# 全Phase依存定義
PHASE_DEPENDENCIES = {
    PhaseID.PRE_0_DOWNLOAD: PhaseDependency(
        phase_id=PhaseID.PRE_0_DOWNLOAD,
        required_files=[],
        required_job_fields=["source.url"],
        required_env_vars=[],
        estimated_duration_min=5.0
    ),
    PhaseID.PRE_1_NORMALIZE: PhaseDependency(
        phase_id=PhaseID.PRE_1_NORMALIZE,
        required_files=["original.wav"],
        required_job_fields=["media.duration_sec"],
        required_env_vars=[],
        estimated_duration_min=10.0
    ),
    PhaseID.PRE_2_SEPARATE: PhaseDependency(
        phase_id=PhaseID.PRE_2_SEPARATE,
        required_files=["normalized.wav"],
        required_job_fields=["media.duration_sec"],
        required_env_vars=[],
        estimated_duration_min=60.0  # Demucs重い
    ),
    PhaseID.PRE_3_WHISPERX: PhaseDependency(
        phase_id=PhaseID.PRE_3_WHISPERX,
        required_files=["pre_voice.wav"],
        required_job_fields=["languages.src_lang"],
        required_env_vars=["HF_TOKEN"],  # Diarization用
        estimated_duration_min=120.0
    ),
    PhaseID.PRE_3_5_VAD: PhaseDependency(
        phase_id=PhaseID.PRE_3_5_VAD,
        required_files=["pre_voice.wav"],
        required_job_fields=["segments"],
        required_env_vars=[],
        estimated_duration_min=15.0
    ),
    PhaseID.PRE_4_REF_AUDIO: PhaseDependency(
        phase_id=PhaseID.PRE_4_REF_AUDIO,
        required_files=["pre_voice.wav"],
        required_job_fields=["segments", "speakers"],
        required_env_vars=[],
        estimated_duration_min=5.0
    ),
    PhaseID.PRE_5_HALLUCINATION: PhaseDependency(
        phase_id=PhaseID.PRE_5_HALLUCINATION,
        required_files=[],
        required_job_fields=["segments", "languages.src_lang"],
        required_env_vars=[],
        estimated_duration_min=2.0
    ),
}

def get_dependency(phase_id: PhaseID) -> PhaseDependency:
    """Phase依存情報取得"""
    return PHASE_DEPENDENCIES[phase_id]

def validate_phase_preconditions(
    phase_id: PhaseID,
    job_id: str,
    job: dict,
    temp_dir: Path
) -> tuple[bool, Optional[str]]:
    """
    Phase実行前の前提条件検証
    Returns: (成功/失敗, エラーメッセージ)
    Design原則: 15. エラーを回避する
    """
    import os
    
    dep = get_dependency(phase_id)
    
    # ファイル存在チェック
    for filename in dep.required_files:
        file_path = temp_dir / filename
        if not file_path.exists():
            return False, f"必須ファイル '{filename}' が見つかりません（前のPhaseが失敗している可能性があります）"
    
    # job.jsonフィールドチェック
    for field_path in dep.required_job_fields:
        keys = field_path.split('.')
        current = job
        
        for key in keys:
            if not isinstance(current, dict) or key not in current:
                return False, f"job.jsonに必須フィールド '{field_path}' がありません"
            current = current[key]
    
    # 環境変数チェック
    for env_var in dep.required_env_vars:
        if not os.getenv(env_var):
            return False, f"環境変数 '{env_var}' が設定されていません（.envファイルを確認してください）"
    
    return True, None
    
# 翻訳Phase追加
PHASE_DEPENDENCIES[PhaseID.TRANSLATION] = PhaseDependency(
    phase_id=PhaseID.TRANSLATION,
    required_files=[],
    required_job_fields=["segments", "languages.src_lang", "languages.tgt_lang"],
    required_env_vars=["GROQ_API_KEY"],
    estimated_duration_min=20.0  # APIコール主体なので比較的速い
)
# TTS Phase追加
PHASE_DEPENDENCIES[PhaseID.TTS] = PhaseDependency(
    phase_id=PhaseID.TTS,
    required_files=["pre_voice.wav"],  # タイミング測定用
    required_job_fields=["segments", "speakers", "languages.tgt_lang"],
    required_env_vars=["HF_TOKEN"],  # Qwen3-TTSモデルダウンロード用
    estimated_duration_min=180.0  # 3時間（CPU処理、100セグメント想定）
)