"""
Qwen3-TTS 1.7B クライアント
Design原則: 18. 複雑性をシステム側へ
"""
import torch
import torchaudio
import logging
from pathlib import Path
from typing import Optional, Tuple
import gc

from config.settings import settings

logger = logging.getLogger(__name__)

class QwenTTSError(Exception):
    """Qwen3-TTS エラー"""
    pass

class QwenTTSClient:
    """
    Qwen3-TTS 1.7B クライアント（CPU専用）
    Design原則: 14. プリコンピュテーション - float32で安定動作
    """
    
    def __init__(self):
        self.device = "cpu"
        self.dtype = torch.float32
        self.model = None
        self.sample_rate = 24000  # Qwen3-TTSのデフォルト
        
        # モデルは遅延ロード（メモリ節約）
        self._model_loaded = False
    
    def _load_model(self):
        """モデル遅延ロード"""
        if self._model_loaded:
            return
        
        try:
            logger.info("Loading Qwen3-TTS model (CPU mode, this may take 1-2 minutes)")
            
            # Qwen3-TTSモデルロード
            # 注：2026年2月時点での仮想的なAPI、実際のAPIに合わせて調整が必要
            from qwen_tts import QwenTTS
            
            self.model = QwenTTS.from_pretrained(
                "Qwen/Qwen3-TTS-1.7B",
                torch_dtype=self.dtype,
                device_map=self.device,
                token=settings.HF_TOKEN
            )
            
            self._model_loaded = True
            logger.info("Qwen3-TTS model loaded successfully")
            
        except Exception as e:
            raise QwenTTSError(f"Failed to load Qwen3-TTS model: {str(e)}")
    
    def synthesize(
        self,
        text: str,
        ref_audio_path: Optional[Path],
        ref_text: Optional[str],
        language: str,
        output_path: Path
    ) -> float:
        """
        音声合成
        
        Args:
            text: 合成するテキスト
            ref_audio_path: 参照音声パス（話者クローニング用）
            ref_text: 参照音声のテキスト
            language: 言語コード
            output_path: 出力wavファイルパス
        
        Returns:
            生成音声の長さ（秒）
        """
        self._load_model()
        
        try:
            # 参照音声読み込み（話者クローニング）
            if ref_audio_path and ref_audio_path.exists():
                ref_audio, ref_sr = torchaudio.load(str(ref_audio_path))
                
                # リサンプリング（Qwen3-TTSの要求レートに合わせる）
                if ref_sr != self.sample_rate:
                    resampler = torchaudio.transforms.Resample(ref_sr, self.sample_rate)
                    ref_audio = resampler(ref_audio)
                
                # モノラル化
                if ref_audio.shape[0] > 1:
                    ref_audio = ref_audio.mean(dim=0, keepdim=True)
                
                ref_audio = ref_audio.to(self.device)
            else:
                # 参照音声なし（プリセットボイス使用）
                ref_audio = None
                ref_text = None
            
            # テキスト前処理（記号正規化等）
            text = self._preprocess_text(text, language)
            
            # 音声合成
            with torch.no_grad():
                output_audio = self.model.synthesize(
                    text=text,
                    ref_audio=ref_audio,
                    ref_text=ref_text,
                    language=language,
                    speed=1.0
                )
            
            # CPU上のテンソルをnumpy配列に変換
            if isinstance(output_audio, torch.Tensor):
                output_audio = output_audio.cpu().numpy()
            
            # wavファイル保存
            output_path.parent.mkdir(parents=True, exist_ok=True)
            torchaudio.save(
                str(output_path),
                torch.from_numpy(output_audio).unsqueeze(0),
                self.sample_rate
            )
            
            # 生成音声の長さを計算
            duration = output_audio.shape[-1] / self.sample_rate
            
            return duration
            
        except Exception as e:
            raise QwenTTSError(f"TTS synthesis failed: {str(e)}")
    
    def _preprocess_text(self, text: str, language: str) -> str:
        """
        テキスト前処理
        Design原則: 50. ユーザーに厳密さを求めない
        """
        import re
        
        # 改行・余分な空白を除去
        text = re.sub(r'\s+', ' ', text).strip()
        
        # 言語別の正規化
        if language == "ja":
            # 全角英数字を半角に
            text = text.translate(
                str.maketrans(
                    '０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ',
                    '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
                )
            )
        
        # 連続する句読点を削減
        text = re.sub(r'([.!?,;:]){2,}', r'\1', text)
        
        # 空文字チェック
        if not text:
            raise QwenTTSError("Empty text after preprocessing")
        
        return text
    
    def unload_model(self):
        """
        モデルをメモリから解放
        Design原則: 54. フェールセーフ - リソース管理
        """
        if self.model is not None:
            del self.model
            self.model = None
            self._model_loaded = False
            
            # 明示的なガベージコレクション
            gc.collect()
            
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            logger.info("Qwen3-TTS model unloaded from memory")
