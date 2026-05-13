"""TTS 流式合成测试"""
from unittest.mock import AsyncMock, patch

from voice_assistant.audio.tts import EdgeTTSProvider, TTSProvider


class TestTTSStreaming:
    """测试 TTS 流式合成功能"""

    def test_synthesize_stream_exists_on_protocol(self):
        """验证 TTSProvider Protocol 定义了 synthesize_stream"""
        assert hasattr(TTSProvider, 'synthesize_stream')

    def test_synthesize_stream_generator(self):
        """验证 synthesize_stream 返回生成器"""
        provider = EdgeTTSProvider()

        with patch.object(provider, '_synthesize_sentence_async', new_callable=AsyncMock) as mock:
            mock.return_value = b"audio_chunk"
            result = provider.synthesize_stream("你好。世界。")

            # 验证返回的是生成器
            import types
            assert isinstance(result, types.GeneratorType)

    def test_synthesize_stream_splits_sentences(self):
        """验证流式合成按句子分割"""
        provider = EdgeTTSProvider()

        with patch.object(provider, '_synthesize_sentence_async', new_callable=AsyncMock) as mock:
            mock.return_value = b"audio_chunk"
            chunks = list(provider.synthesize_stream("你好。世界。"))

            # 应该分成两句，产生两个 chunk
            assert len(chunks) == 2
            assert mock.call_count == 2

    def test_synthesize_stream_empty_text(self):
        """验证空文本返回空生成器"""
        provider = EdgeTTSProvider()
        chunks = list(provider.synthesize_stream(""))
        assert len(chunks) == 0

    def test_synthesize_stream_single_sentence(self):
        """验证单句文本正确生成"""
        provider = EdgeTTSProvider()

        with patch.object(provider, '_synthesize_sentence_async', new_callable=AsyncMock) as mock:
            mock.return_value = b"single_sentence_audio"
            chunks = list(provider.synthesize_stream("这是一句话。"))

            assert len(chunks) == 1
            assert chunks[0] == b"single_sentence_audio"

    def test_synthesize_stream_with_punctuation(self):
        """验证多种标点符号正确分割"""
        provider = EdgeTTSProvider()

        with patch.object(provider, '_synthesize_sentence_async', new_callable=AsyncMock) as mock:
            mock.return_value = b"chunk"
            # 包含句号、问号、感叹号
            chunks = list(provider.synthesize_stream("你好。吃了吗？很好！"))

            assert len(chunks) == 3

    def test_synthesize_stream_consecutive_punctuation(self):
        """验证连续标点处理 - 预处理后会产生多个调用"""
        provider = EdgeTTSProvider()

        with patch.object(provider, '_synthesize_sentence_async', new_callable=AsyncMock) as mock:
            mock.return_value = b"audio"
            # 连续标点 - 预处理会在标点后添加空格，影响分割
            list(provider.synthesize_stream("你好。。。世界。"))

            # 预处理后实际产生多个句子
            assert mock.call_count >= 2

    def test_synthesize_stream_handles_none_result(self):
        """验证处理 None 结果不抛出异常"""
        provider = EdgeTTSProvider()

        with patch.object(provider, '_synthesize_sentence_async', new_callable=AsyncMock) as mock:
            mock.return_value = None
            chunks = list(provider.synthesize_stream("你好。"))

            # None 结果应该被过滤掉
            assert len(chunks) == 0

    def test_synthesize_stream_error_handling(self):
        """验证流式合成错误处理 - 实现会捕获异常并继续"""
        provider = EdgeTTSProvider()

        with patch.object(provider, '_synthesize_sentence_async', new_callable=AsyncMock) as mock:
            # 模拟部分失败 - 第一句失败，第二句成功
            mock.side_effect = [RuntimeError("合成失败"), b"audio"]
            chunks = list(provider.synthesize_stream("第一句。第二句。"))

            # 实现会捕获 RuntimeError 并继续处理
            assert len(chunks) == 1
            assert chunks[0] == b"audio"

    def test_provider_has_split_sentences_method(self):
        """验证 Provider 有句子分割方法"""
        provider = EdgeTTSProvider()
        assert hasattr(provider, '_split_sentences')

    def test_split_sentences_basic(self):
        """验证基本句子分割"""
        provider = EdgeTTSProvider()
        sentences = provider._split_sentences("第一句。第二句。第三句。")

        assert len(sentences) == 3
        # 实现保留标点符号
        assert sentences[0] == "第一句。"
        assert sentences[1] == "第二句。"
        assert sentences[2] == "第三句。"

    def test_split_sentences_with_whitespace(self):
        """验证带空格的句子分割"""
        provider = EdgeTTSProvider()
        sentences = provider._split_sentences("  第一句  。  第二句  。  ")

        assert len(sentences) == 2
        # 实现会去除首尾空格，但保留内容中的空格和标点
        assert sentences[0] == "第一句  。"
        assert sentences[1] == "第二句  。"
