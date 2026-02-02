"""
翻訳Phase テストケース
Design原則: 89. ユーザーが学習できるようにする
"""
import pytest
from unittest.mock import Mock, patch
from pipeline.phases.trans_groq import TranslationPhase
from pipeline.utils.groq_client import GroqClient, GroqAPIError
from pipeline.utils.chunker import SegmentChunker

class TestGroqClient:
    """GroqClient単体テスト"""
    
    @patch('pipeline.utils.groq_client.Groq')
    def test_translate_success(self, mock_groq_class):
        """正常系：翻訳成功"""
        # モック設定
        mock_response = Mock()
        mock_response.choices = [
            Mock(message=Mock(content='{"translations": [{"id": 0, "translation": "Hello"}]}'))
        ]
        
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_groq_class.return_value = mock_client
        
        # テスト実行
        client = GroqClient(api_key="test_key")
        result = client.translate(["こんにちは"], "ja", "en")
        
        assert result == ["Hello"]
    
    @patch('pipeline.utils.groq_client.Groq')
    def test_translate_retry(self, mock_groq_class):
        """リトライ機能テスト"""
        # 1回目失敗、2回目成功
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = [
            Exception("API Error"),
            Mock(choices=[Mock(message=Mock(content='{"translations": [{"id": 0, "translation": "Hello"}]}'))])
        ]
        mock_groq_class.return_value = mock_client
        
        client = GroqClient(api_key="test_key")
        result = client.translate(["こんにちは"], "ja", "en", max_retries=3)
        
        assert result == ["Hello"]
        assert mock_client.chat.completions.create.call_count == 2
    
    def test_translate_no_api_key(self):
        """API Key未設定エラー"""
        with pytest.raises(GroqAPIError, match="GROQ_API_KEY not set"):
            GroqClient(api_key="")

class TestSegmentChunker:
    """SegmentChunker単体テスト"""
    
    def test_chunk_by_char_limit(self):
        """文字数制限でチャンク分割"""
        segments = [
            {"src_text": "a" * 1000},
            {"src_text": "b" * 1500},
            {"src_text": "c" * 800},
        ]
        
        chunks = SegmentChunker.chunk_segments(segments, char_limit=2000, seg_limit=100)
        
        # 1つ目のチャンク: "a"*1000 + "b"*1500 = 2500 > 2000なので分割
        assert len(chunks) == 2
        assert len(chunks) == 1
        assert len(chunks) == 2[3]
    
    def test_chunk_by_seg_limit(self):
        """セグメント数制限でチャンク分割"""
        segments = [{"src_text": "test"} for _ in range(50)]
        
        chunks = SegmentChunker.chunk_segments(segments, char_limit=100000, seg_limit=20)
        
        assert len(chunks) == 3  # 50 / 20 = 2.5 → 3チャンク
        assert len(chunks) == 20
        assert len(chunks) == 20[3]
        assert len(chunks) == 10[4]

# 実行方法:
# pytest tests/test_translation.py -v
