"""
Phase Pre-5: ハルシネーション判定
Design原則: 56. 可能性と確率を区別する
"""
from collections import Counter
import re

from pipeline.base_phase import BasePhase, PhaseResult, PhaseError
from app.services.storage import load_job
from config.settings import settings

class HallucinationPhase(BasePhase):
    """
    ハルシネーション（幻聴）セグメントを検出
    
    入力: segments[]
    成果物: segments[].flags.suspected_hallucination 更新
    """
    
    def get_phase_name(self) -> str:
        return "Pre-5: Hallucination"
    
    def get_timeout(self) -> int:
        return 300  # 5分（計算処理のみ）
    
    def validate_inputs(self) -> None:
        """入力検証"""
        job = load_job(self.job_id)
        if not job.get("segments"):
            raise PhaseError("segments が存在しません")
    
    def execute(self) -> PhaseResult:
        """ハルシネーション判定実行"""
        job = load_job(self.job_id)
        segments = job["segments"]
        src_lang = job["languages"]["src_lang"]
        
        try:
            # 定型句リスト（言語別）
            COMMON_PHRASES = self._get_common_phrases(src_lang)
            
            # 全セグメントのテキストを集計（TF-IDF風）
            all_texts = [seg["src_text"].lower() for seg in segments]
            phrase_counter = Counter()
            
            for text in all_texts:
                # 3-gram以上のフレーズを抽出
                words = re.findall(r'\w+', text)
                for i in range(len(words) - 2):
                    phrase = ' '.join(words[i:i+3])
                    phrase_counter[phrase] += 1
            
            # 頻出フレーズ（全体の20%以上で出現）
            total_segs = len(segments)
            threshold = total_segs * 0.2
            frequent_phrases = {
                phrase for phrase, count in phrase_counter.items()
                if count >= threshold
            }
            
            self.logger.info(f"Detected {len(frequent_phrases)} frequent phrases (potential hallucinations)")
            
            # 各セグメントを判定
            hallucination_count = 0
            
            for seg in segments:
                text = seg["src_text"].lower()
                is_hallucination = False
                
                # 1. 定型句チェック
                for phrase in COMMON_PHRASES:
                    if phrase in text:
                        is_hallucination = True
                        break
                
                # 2. 頻出フレーズチェック
                if not is_hallucination:
                    for phrase in frequent_phrases:
                        if phrase in text:
                            is_hallucination = True
                            break
                
                # 3. 異常に短いセグメント（<2文字）
                if len(seg["src_text"].strip()) < 2:
                    is_hallucination = True
                
                # 4. Whisper no_speech_prob が高い
                no_speech_prob = seg.get("whisper", {}).get("no_speech_prob", 0.0)
                if no_speech_prob > 0.7:
                    is_hallucination = True
                
                seg["flags"]["suspected_hallucination"] = is_hallucination
                
                if is_hallucination:
                    hallucination_count += 1
            
            self.logger.info(
                f"Hallucination detection completed: "
                f"{hallucination_count}/{total_segs} segments flagged"
            )
            
            return PhaseResult(
                success=True,
                output_files={},
                metadata={"segments": segments}
            )
            
        except Exception as e:
            self.logger.error(f"Hallucination detection failed: {e}")
            raise PhaseError(f"ハルシネーション判定に失敗しました: {str(e)}")
    
    def _get_common_phrases(self, lang: str) -> list[str]:
        """言語別の定型句リスト"""
        PHRASES = {
            "ja": [
                "ご視聴ありがとうございました",
                "チャンネル登録",
                "高評価",
                "コメント欄",
                "次回",
                "字幕"
            ],
            "en": [
                "thank you for watching",
                "subscribe",
                "like and subscribe",
                "comment below",
                "next video",
                "subtitles"
            ],
            "zh": [
                "感谢观看",
                "订阅",
                "点赞",
                "评论",
                "下一期"
            ],
            # 他言語は必要に応じて追加
        }
        
        return PHRASES.get(lang, [])
    
    def validate_outputs(self, result: PhaseResult) -> None:
        """成果物検証"""
        if "segments" not in result.meta
            raise PhaseError("segments が更新されていません")
        
        # 全セグメントに suspected_hallucination が設定されているか
        segments = result.metadata["segments"]
        for seg in segments[:5]:
            if "suspected_hallucination" not in seg.get("flags", {}):
                raise PhaseError(f"セグメント {seg['seg_id']} に suspected_hallucination フラグがありません")

def phase_hallucination(job_id: str) -> None:
    """Phase Pre-5 実行"""
    phase = HallucinationPhase(job_id)
    result = phase.run()
    
    if not result.success:
        raise PhaseError(result.error)
