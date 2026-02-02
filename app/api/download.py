"""
納品物ダウンロードAPI（PIN認証追加）
Design原則: 13. コンストレイント - 制約で誤操作を防ぐ
"""
from fastapi import APIRouter, HTTPException, Request, Header
from fastapi.responses import FileResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
import zipfile
from pathlib import Path
from datetime import datetime
import json

from config.settings import settings
from app.services.storage import load_job, save_job
from app.services.notification import PINManager

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

@router.get("/jobs/{job_id}/download")
@limiter.limit(f"{settings.RATE_LIMIT_DOWNLOADS_PER_MINUTE}/minute")
async def download_job(
    request: Request, 
    job_id: str,
    x_pin: str = Header(..., alias="X-PIN")  # Design原則: 13. コンストレイント
):
    """
    納品物ダウンロード（PIN認証必須）
    """
    job_path = settings.JOBS_DIR / f"{job_id}.json"
    if not job_path.exists():
        raise HTTPException(status_code=404, detail="ジョブが見つかりません")
    
    # PIN検証（Design原則: 15. エラーを回避する）
    is_valid, error_msg = PINManager.verify_pin(job_id, x_pin)
    if not is_valid:
        raise HTTPException(status_code=403, detail=error_msg)
    
    job = load_job(job_id)
    
    # ステータス確認
    if job["status"] != "COMPLETED":
        raise HTTPException(
            status_code=400,
            detail=f"ダウンロード不可: ステータスが '{job['status']}' です"
        )
    
    # 期限確認
    if job.get("expires_at"):
        expires = datetime.fromisoformat(job["expires_at"].replace("Z", "+00:00"))
        if datetime.utcnow() > expires:
            raise HTTPException(
                status_code=410,
                detail="納品物は保持期限切れで削除されました"
            )
    
    # ダウンロード回数チェック
    if job.get("download_count", 0) >= 5:
        raise HTTPException(
            status_code=429,
            detail="ダウンロード回数上限に達しました（最大5回）"
        )
    
    # ZIPファイル作成
    output_dir = settings.OUTPUT_DIR / job_id
    if not output_dir.exists():
        raise HTTPException(
            status_code=500,
            detail="納品物が見つかりません（内部エラー）"
        )
    
    zip_path = settings.TEMP_DIR / f"dub_{job_id}.zip"
    create_delivery_zip(output_dir, zip_path, job)
    
    # ダウンロード回数を更新
    job["download_count"] = job.get("download_count", 0) + 1
    save_job(job)
    
    return FileResponse(
        path=zip_path,
        media_type="application/zip",
        filename=f"talkdub_{job['languages']['tgt_lang']}.zip",
        headers={
            "X-Download-Count": str(job["download_count"]),
            "X-Expires-At": job.get("expires_at", "")
        }
    )

def create_delivery_zip(output_dir: Path, zip_path: Path, job: dict):
    """納品ZIPファイル作成"""
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        # dub_*.wav
        dub_wav = output_dir / f"dub_{job['languages']['tgt_lang']}.wav"
        if dub_wav.exists():
            zf.write(dub_wav, dub_wav.name)
        
        # manifest.json
        manifest = output_dir / "manifest.json"
        if manifest.exists():
            zf.write(manifest, manifest.name)
        
        # segments_*.json
        segments = output_dir / f"segments_{job['languages']['tgt_lang']}.json"
        if segments.exists():
            zf.write(segments, segments.name)
        
        # UPLOAD_GUIDE.txt
        guide_text = generate_upload_guide(job)
        zf.writestr("UPLOAD_GUIDE.txt", guide_text)
        
        # README.txt
        readme_text = generate_readme(job)
        zf.writestr("README.txt", readme_text)

def generate_upload_guide(job: dict) -> str:
    """YouTube Studio アップロード手順書"""
    return f"""
# YouTube Studio 多言語音声トラック アップロード手順

## 1. YouTube Studio にサインイン
https://studio.youtube.com

## 2. 左メニューから「Languages」を選択

## 3. 対象動画を選択
動画ID: {job['source']['video_id']}
URL: {job['source']['url']}

## 4. 言語を追加
「Add Language」→ {job['languages']['tgt_lang']} を選択

## 5. 音声トラックをアップロード
「Dub」の横の「Add」→「Select file」
→ dub_{job['languages']['tgt_lang']}.wav を選択

## 6. 公開
「Publish」をクリック

## 注意事項
- すでに自動吹替（auto dub）がある場合は、先にそれを削除してください
- 音声トラックは動画と同じ長さに調整済みです
- アップロード後、反映まで数分かかる場合があります

---
TalkDub - 多言語音声変換プラットフォーム
"""

def generate_readme(job: dict) -> str:
    """納品物説明"""
    return f"""
# TalkDub 納品物

## ジョブ情報
- ジョブID: {job['job_id']}
- 作成日時: {job['created_at']}
- 元言語: {job['languages']['src_lang']}
- 翻訳先言語: {job['languages']['tgt_lang']}

## ファイル構成
- dub_{job['languages']['tgt_lang']}.wav: 吹き替え音声（YouTube用）
- manifest.json: 処理メタデータ（統計情報含む）
- segments_{job['languages']['tgt_lang']}.json: セグメント詳細（検収用）
- UPLOAD_GUIDE.txt: YouTube Studioへのアップロード手順

## 注意事項
- 本ファイルは72時間で削除されます
- 品質保証なし（研究プロジェクトのため）
- 口パク（リップシンク）には対応していません
- 問題があればフィードバックをお願いします

## 技術詳細
- ASR: WhisperX
- TTS: Qwen3-TTS 1.7B
- 処理サーバー: CPU専用（非GPU）
- 翻訳: Groq API

---
TalkDub - https://talkdub.lab
"""
