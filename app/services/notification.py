"""
メール通知サービス（完全非同期版）
Design原則: 90. UIをロックしない
"""
import resend
import asyncio
import logging
from typing import Optional

from config.settings import settings
from app.services.pin_manager import pin_manager

logger = logging.getLogger(__name__)

# Resend API Key設定
resend.api_key = settings.RESEND_API_KEY

async def send_job_created_email(
    job_id: str, 
    email: str, 
    video_url: str, 
    src_lang: str, 
    tgt_lang: str
) -> bool:
    """ジョブ作成通知メール送信（非同期）"""
    pin = pin_manager.generate_pin(job_id)
    
    try:
        # Resend APIは同期なので、別スレッドで実行
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: resend.Emails.send({
                "from": settings.EMAIL_FROM,
                "to": [email],
                "subject": "【TalkDub】処理を開始しました",
                "html": render_job_created_html(job_id, pin, video_url, src_lang, tgt_lang)
            })
        )
        
        logger.info(f"Job created email sent: job_id={job_id}, resend_id={response['id']}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send job created email: {e}")
        return False

async def send_job_completed_email(
    job_id: str, 
    email: str, 
    download_url: str, 
    expires_at: str
) -> bool:
    """処理完了通知メール送信（非同期）"""
    pin_data = pin_manager.redis.hgetall(f"talkdub:pin:{job_id}")
    pin = pin_data.get("pin", "N/A")
    
    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: resend.Emails.send({
                "from": settings.EMAIL_FROM,
                "to": [email],
                "subject": "【TalkDub】処理が完了しました",
                "html": render_job_completed_html(job_id, pin, download_url, expires_at)
            })
        )
        
        logger.info(f"Job completed email sent: job_id={job_id}, resend_id={response['id']}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send job completed email: {e}")
        return False

async def send_job_failed_email(
    job_id: str, 
    email: str, 
    error_message: str
) -> bool:
    """処理失敗通知メール送信（非同期）"""
    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: resend.Emails.send({
                "from": settings.EMAIL_FROM,
                "to": [email],
                "subject": "【TalkDub】処理が失敗しました",
                "html": render_job_failed_html(job_id, error_message)
            })
        )
        
        logger.info(f"Job failed email sent: job_id={job_id}, resend_id={response['id']}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send job failed email: {e}")
        return False

def render_job_created_html(job_id: str, pin: str, video_url: str, src_lang: str, tgt_lang: str) -> str:
    """
    ジョブ作成通知HTMLテンプレート
    Design原則: 11. ユーザーの言葉を使う
    """
    return f"""
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.6; color: #1f2937; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #2563eb; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
        .content {{ background: #ffffff; padding: 30px; border: 1px solid #e5e7eb; }}
        .pin-box {{ background: #f9fafb; border: 2px solid #2563eb; padding: 20px; text-align: center; margin: 20px 0; border-radius: 8px; }}
        .pin-code {{ font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #2563eb; }}
        .button {{ display: inline-block; background: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin: 10px 0; }}
        .footer {{ text-align: center; color: #6b7280; font-size: 14px; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎙️ TalkDub</h1>
            <p>多言語音声変換プラットフォーム</p>
        </div>
        
        <div class="content">
            <h2>処理を開始しました</h2>
            
            <p>以下のジョブを受け付けました：</p>
            
            <ul>
                <li><strong>ジョブID:</strong> {job_id}</li>
                <li><strong>動画URL:</strong> {video_url}</li>
                <li><strong>言語:</strong> {src_lang} → {tgt_lang}</li>
            </ul>
            
            <div class="pin-box">
                <p><strong>ダウンロード用PINコード</strong></p>
                <div class="pin-code">{pin}</div>
                <p style="margin-top:10px; font-size:14px; color:#6b7280;">
                    処理完了後、このPINコードを入力してダウンロードしてください<br>
                    有効期限: 72時間
                </p>
            </div>
            
            <p><strong>処理時間の目安:</strong> 15〜20時間（30分動画の場合）</p>
            
            <p>処理完了時に再度メールでお知らせします。</p>
            
            <a href="https://talkdub.lab/status/{job_id}" class="button">ステータスを確認</a>
        </div>
        
        <div class="footer">
            <p>このメールは TalkDub から自動送信されています</p>
            <p>研究プロジェクトのため、品質保証はありません</p>
        </div>
    </div>
</body>
</html>
"""


def render_job_completed_html(job_id: str, pin: str, download_url: str, expires_at: str) -> str:
    """処理完了通知HTMLテンプレート"""
    return f"""
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.6; color: #1f2937; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #16a34a; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
        .content {{ background: #ffffff; padding: 30px; border: 1px solid #e5e7eb; }}
        .pin-reminder {{ background: #fef3c7; border-left: 4px solid #f59e0b; padding: 15px; margin: 20px 0; }}
        .button {{ display: inline-block; background: #16a34a; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin: 10px 0; }}
        .footer {{ text-align: center; color: #6b7280; font-size: 14px; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>✅ 処理完了</h1>
        </div>
        
        <div class="content">
            <h2>納品物の準備ができました</h2>
            
            <p>ジョブID <strong>{job_id}</strong> の処理が完了しました。</p>
            
            <div class="pin-reminder">
                <strong>📌 PINコード: {pin}</strong><br>
                ダウンロード時に必要です
            </div>
            
            <p><strong>⚠️ 重要:</strong></p>
            <ul>
                <li>納品物は <strong>{expires_at}</strong> まで保持されます</li>
                <li>期限後は自動削除されます（再生成不可）</li>
                <li>ダウンロードは最大5回まで可能です</li>
            </ul>
            
            <a href="{download_url}" class="button">今すぐダウンロード</a>
            
            <p style="margin-top:30px; font-size:14px; color:#6b7280;">
                納品物にはYouTube Studioへのアップロード手順書が含まれています
            </p>
        </div>
        
        <div class="footer">
            <p>TalkDub - 研究プロジェクト</p>
        </div>
    </div>
</body>
</html>
"""


def render_job_failed_html(job_id: str, error_message: str) -> str:
    """処理失敗通知HTMLテンプレート"""
    return f"""
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.6; color: #1f2937; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #dc2626; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
        .content {{ background: #ffffff; padding: 30px; border: 1px solid #e5e7eb; }}
        .error-box {{ background: #fef2f2; border-left: 4px solid #dc2626; padding: 15px; margin: 20px 0; }}
        .footer {{ text-align: center; color: #6b7280; font-size: 14px; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>❌ 処理失敗</h1>
        </div>
        
        <div class="content">
            <h2>処理中にエラーが発生しました</h2>
            
            <p>ジョブID <strong>{job_id}</strong> の処理が失敗しました。</p>
            
            <div class="error-box">
                <strong>エラー内容:</strong><br>
                {error_message}
            </div>
            
            <p><strong>考えられる原因:</strong></p>
            <ul>
                <li>動画が削除された、または非公開になっている</li>
                <li>年齢制限・地域制限がある</li>
                <li>音声が極端に長い、または品質が低い</li>
                <li>サーバーリソース不足（一時的）</li>
            </ul>
            
            <p>再試行する場合は、しばらく時間をおいてから再投稿してください。</p>
        </div>
        
        <div class="footer">
            <p>TalkDub - 研究プロジェクト</p>
            <p>フィードバックは Discord でお待ちしています</p>
        </div>
    </div>
</body>
</html>
"""
