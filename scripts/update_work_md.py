"""
work.md 自動更新スクリプト
Design原則: 29. 唯一の選択は自動化する
"""
import re
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent
WORK_MD = PROJECT_ROOT / "work.md"

# Phase定義（実装時に追加）
PHASES = {
    "インフラ": [
        ("プロジェクト構造", "✅", "ディレクトリ構成、命名規則"),
        ("設定管理", "✅", "config/settings.py v0.1.2"),
        ("JSON Schema", "✅", "job.json, translation_patch.json"),
        ("ストレージ管理", "✅", "app/services/storage.py, atomic write"),
        ("バリデーション", "✅", "app/utils/validation.py"),
        ("ログ管理", "✅", "構造化ログ、contextual logging"),
    ],
    "Web UI/API": [
        ("FastAPI本体", "✅", "app/main.py, セキュリティヘッダー"),
        ("ジョブ投稿API", "✅", "POST /api/v1/jobs, レート制限"),
        ("ステータスAPI", "✅", "GET /api/v1/jobs/{id}/status"),
        ("ダウンロードAPI", "✅", "GET /api/v1/jobs/{id}/download, PIN認証"),
        ("フロントエンド", "✅", "HTML/CSS/JS, Design.md準拠"),
    ],
    "前処理": [
        ("Phase Pre-0", "✅", "YouTube DL (yt-dlp) + BasePhase"),
        ("Phase Pre-1", "✅", "音声正規化 + BasePhase"),
        ("Phase Pre-2", "❌", "BGM分離 (Demucs)"),
        ("Phase Pre-3", "❌", "WhisperX (ASR + Diarization)"),
        ("Phase Pre-3.5", "❌", "Silero VAD"),
        ("Phase Pre-4", "❌", "ref_audio抽出"),
        ("Phase Pre-5", "❌", "ハルシネーション判定"),
    ],
    "翻訳": [
        ("Translation", "❌", "Groq API, チャンク分割"),
    ],
    "TTS": [
        ("TTS", "❌", "Qwen3-TTS 1.7B CPU"),
    ],
    "後処理": [
        ("Post-1 Timeline", "❌", "タイムライン計算"),
        ("Post-2 Mix", "❌", "音声結合"),
        ("Post-3 Finalize", "❌", "動画尺一致"),
        ("Post-4 Manifest", "❌", "manifest.json生成"),
    ],
    "運用": [
        ("PIN管理", "✅", "Redis永続化 + pin_manager"),
        ("メール通知", "✅", "Resend API, 完全非同期化"),
        ("ジョブキュー", "✅", "Celery, Redis broker"),
        ("Celeryタスク", "✅", "pipeline/tasks.py, orchestrator"),
        ("パイプライン基盤", "✅", "BasePhase抽象クラス, PhaseResult"),
        ("自動削除cron", "❌", "期限切れジョブ/PIN削除"),
        ("Cloudflared", "✅", "Tunnel設定, docker-compose"),
        ("監視・アラート", "❌", "ディスク/キュー監視"),
    ],
}

def count_progress() -> dict:
    """進捗を集計"""
    stats = {"completed": 0, "total": 0}
    
    for category, tasks in PHASES.items():
        for name, status, desc in tasks:
            stats["total"] += 1
            if status == "✅":
                stats["completed"] += 1
    
    stats["percentage"] = int(stats["completed"] / stats["total"] * 100)
    return stats

def generate_work_md() -> str:
    """work.mdの内容を生成"""
    stats = count_progress()
    now = datetime.now().strftime("%Y-%m-%d %H:%M JST")
    
    content = f"""# TalkDub 実装進捗管理

最終更新: {now}

## プロジェクト概要
- **名称**: TalkDub
- **バージョン**: 0.1.2 (リファクタ版)
- **目的**: YouTube動画の多言語音声吹き替え自動化（研究プロジェクト）
- **アーキテクチャ**: FastAPI + Celery + Redis + Cloudflared

---

## 全体進捗: {stats['percentage']}% ({stats['completed']}/{stats['total']} 完了)

### フェーズ別進捗

"""
    
    # カテゴリ別の表を生成
    for category, tasks in PHASES.items():
        completed = sum(1 for _, status, _ in tasks if status == "✅")
        total = len(tasks)
        percentage = int(completed / total * 100) if total > 0 else 0
        
        content += f"#### {category} ({completed}/{total} - {percentage}%)\n\n"
        content += "| # | 項目 | 状態 | 実装内容 |\n"
        content += "|---|------|------|----------|\n"
        
        for i, (name, status, desc) in enumerate(tasks, 1):
            content += f"| {i} | {name} | {status} | {desc} |\n"
        
        content += "\n"
    
    content += f"""
---

## リファクタリング履歴

### v0.1.2 (2026-02-02 21:33)
- ✅ BasePhase抽象クラス導入（エラーハンドリング統一）
- ✅ PhaseResult型定義（型安全性向上）
- ✅ PipelineOrchestrator実装（Celeryタスク簡略化）
- ✅ メール送信完全非同期化
- ✅ タイムアウト設定の集約化
- ✅ 構造化ログの改善
- ✅ Phase Pre-0, Pre-1をBasePhaseベースに移行

### v0.1.1 (2026-02-02 21:25)
- ✅ PIN管理Redis永続化
- ✅ ストレージサービス実装
- ✅ バリデーションユーティリティ
- ✅ work.md追加

### v0.1.0 (2026-02-02 20:08)
- ✅ 初期実装（FastAPI + Celery）

---

## 次のマイルストーン

### Phase 1: MVP完成 (目標: 2026-02-12)
- [ ] Phase Pre-2〜Pre-5 実装（BasePhaseベース）
- [ ] 翻訳 Phase 実装
- [ ] TTS Phase 実装
- [ ] 後処理 Phase Post-1〜Post-4 実装
- [ ] E2Eテスト（1本の動画で完走）

---

最終更新: {now}
"""
    
    return content

def update_work_md():
    """work.mdを更新"""
    content = generate_work_md()
    WORK_MD.write_text(content, encoding="utf-8")
    print(f"✅ work.md updated: {WORK_MD}")

if __name__ == "__main__":
    update_work_md()
