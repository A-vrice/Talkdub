"""
エラーメッセージのユーザーフレンドリー化
Design原則: 11. ユーザーの言葉を使う
"""
import re

class ErrorTranslator:
    """
    技術的エラーメッセージをユーザー向けに翻訳
    Design原則: 55. エラー表示は建設的にする
    """
    
    # エラーパターンと翻訳
    TRANSLATIONS = [
        # yt-dlp関連
        (r"ERROR: \\[youtube\\] .+: Video unavailable", 
         "動画が視聴できません（削除済み、非公開、または地域制限の可能性があります）"),
        
        (r"ERROR: \\[youtube\\] .+: This video requires payment",
         "この動画は有料コンテンツのため処理できません"),
        
        (r"ERROR: \\[youtube\\] .+: Sign in to confirm your age",
         "この動画は年齢確認が必要なため処理できません"),
        
        # ffmpeg関連
        (r"Invalid data found when processing input",
         "音声ファイルの形式が正しくありません（ファイルが破損している可能性があります）"),
        
        (r"Conversion failed",
         "音声変換に失敗しました（ファイル形式が対応していない可能性があります）"),
        
        # Demucs関連
        (r"RuntimeError: The size of tensor .+ must match",
         "音声分離処理でメモリ不足が発生しました（動画が長すぎる可能性があります）"),
        
        # WhisperX関連
        (r"No speech found in audio",
         "音声が検出されませんでした（無音、またはノイズのみの可能性があります）"),
        
        (r"Language .+ not supported",
         "指定された言語はサポートされていません"),
        
        # 一般的なエラー
        (r"Timeout",
         "処理時間が上限を超えました（動画が長すぎる、またはサーバーが高負荷の可能性があります）"),
        
        (r"Out of memory|OOM",
         "メモリ不足が発生しました（動画が長すぎる、または同時処理数が多い可能性があります）"),
        
        (r"Connection (?:refused|timeout|reset)",
         "ネットワーク接続に失敗しました（一時的な障害の可能性があります。しばらく待ってから再試行してください）"),
    ]
    
    @classmethod
    def translate(cls, technical_error: str) -> str:
        """
        技術的エラーを翻訳
        
        Args:
            technical_error: 元のエラーメッセージ
        
        Returns:
            ユーザー向けエラーメッセージ
        """
        # パターンマッチング
        for pattern, translation in cls.TRANSLATIONS:
            if re.search(pattern, technical_error, re.IGNORECASE):
                return translation
        
        # マッチしない場合は元のメッセージを簡略化
        # （技術的詳細を除去）
        simplified = re.sub(r'\\[.*?\\]', '', technical_error)
        simplified = re.sub(r'File ".*?", line \d+', '', simplified)
        simplified = simplified.strip()
        
        if len(simplified) > 200:
            simplified = simplified[:200] + "..."
        
        return simplified or "予期しないエラーが発生しました"
