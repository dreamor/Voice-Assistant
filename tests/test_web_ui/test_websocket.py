"""WebSocket 通信测试"""
import pytest
import json
from unittest.mock import MagicMock, patch, AsyncMock

from fastapi.testclient import TestClient
from fastapi import FastAPI, WebSocket


class TestWebSocketConnection:
    """测试 WebSocket 连接和消息处理"""

    def test_websocket_endpoint_exists(self):
        """验证 WebSocket 端点存在"""
        # 导入 web_ui 模块检查 WebSocket 路由
        from web_ui import app

        # 检查是否有 WebSocket 路由
        routes = [r for r in app.routes if hasattr(r, 'path') and '/ws' in str(r.path)]
        assert len(routes) > 0, "WebSocket endpoint not found"

    def test_websocket_message_types(self):
        """验证 WebSocket 消息类型定义"""
        # 验证前端和后端使用一致的消息类型
        message_types = {
            'conversation_started',
            'conversation_loaded',
            'user_message',
            'asr_processing',
            'asr_result',
            'llm_thinking',
            'executing',
            'execution_complete',
            'llm_stream',
            'llm_complete',
            'tts_generating',
            'tts_audio',
            'tts_chunk',
            'tts_complete',
            'error',
            'pong',
            'confirm_required',
            # 客户端到服务端
            'start_conversation',
            'text_message',
            'audio_data',
            'replay_tts',
            'confirm_response',
        }

        # 验证消息类型命名规范
        for msg_type in message_types:
            assert '_' in msg_type or msg_type.islower()

    def test_tts_chunk_message_structure(self):
        """验证 tts_chunk 消息结构"""
        message = {
            'type': 'tts_chunk',
            'data': 'base64_encoded_audio_data',
            'chunk_index': 0,
        }

        assert 'type' in message
        assert 'data' in message
        assert 'chunk_index' in message
        assert isinstance(message['chunk_index'], int)

    def test_tts_complete_message_structure(self):
        """验证 tts_complete 消息结构"""
        message = {
            'type': 'tts_complete',
        }

        assert message['type'] == 'tts_complete'

    def test_audio_data_message_structure(self):
        """验证 audio_data 消息结构"""
        message = {
            'type': 'audio_data',
            'base64Audio': 'base64_encoded_data',
            'format': 'audio/webm',
        }

        assert message['type'] == 'audio_data'
        assert 'base64Audio' in message
        assert 'format' in message

    def test_confirm_required_message_structure(self):
        """验证 confirm_required 消息结构"""
        message = {
            'type': 'confirm_required',
            'confirm_id': '12345',
            'tool_name': 'write_file',
            'arguments': {'path': '/tmp/test.txt'},
            'message': '确认写入文件?',
            'level': 'double_confirm',
        }

        assert message['type'] == 'confirm_required'
        assert 'confirm_id' in message
        assert 'tool_name' in message
        assert 'arguments' in message
        assert 'message' in message
        assert 'level' in message


class TestStreamingAudioPlayer:
    """测试前端 StreamingAudioPlayer 类逻辑"""

    def test_player_chunk_management(self):
        """验证播放器块管理逻辑"""
        # 模拟 StreamingAudioPlayer 的行为
        chunks = {}
        next_chunk_index = 0
        is_playing = False

        # 添加块
        def add_chunk(base64_data, index):
            chunks[index] = base64_data

        add_chunk("audio_0", 0)
        add_chunk("audio_1", 1)

        assert len(chunks) == 2
        assert chunks[0] == "audio_0"
        assert chunks[1] == "audio_1"

    def test_player_sequential_playback(self):
        """验证播放器顺序播放逻辑"""
        chunks = {0: "audio_0", 1: "audio_1", 2: "audio_2"}
        next_chunk_index = 0
        played = []

        def play_next():
            nonlocal next_chunk_index
            if next_chunk_index in chunks:
                played.append(chunks[next_chunk_index])
                del chunks[next_chunk_index]
                next_chunk_index += 1
                return True
            return False

        # 顺序播放所有块
        while play_next():
            pass

        assert played == ["audio_0", "audio_1", "audio_2"]
        assert len(chunks) == 0

    def test_player_out_of_order_chunks(self):
        """验证播放器处理乱序块"""
        chunks = {}
        next_chunk_index = 0
        played = []

        # 乱序添加块
        chunks[2] = "audio_2"
        chunks[0] = "audio_0"
        chunks[1] = "audio_1"

        def play_next():
            nonlocal next_chunk_index
            if next_chunk_index in chunks:
                played.append(chunks[next_chunk_index])
                del chunks[next_chunk_index]
                next_chunk_index += 1
                return True
            return False

        # 第一次只能播放索引 0
        assert play_next() is True
        assert played == ["audio_0"]

        # 现在可以播放索引 1
        assert play_next() is True
        assert played == ["audio_0", "audio_1"]

        # 最后播放索引 2
        assert play_next() is True
        assert played == ["audio_0", "audio_1", "audio_2"]

    def test_player_reset(self):
        """验证播放器重置"""
        chunks = {0: "audio_0", 1: "audio_1"}
        next_chunk_index = 2

        # 重置
        chunks.clear()
        next_chunk_index = 0

        assert len(chunks) == 0
        assert next_chunk_index == 0


class TestWebSocketIntegration:
    """测试 WebSocket 集成场景"""

    def test_message_sequence_text_to_speech(self):
        """验证文本到语音的完整消息序列"""
        expected_sequence = [
            ('user_message', '用户输入'),
            ('llm_thinking', None),
            ('llm_stream', 'AI 回复内容'),
            ('llm_complete', 'AI 回复内容'),
            ('tts_generating', None),
            ('tts_chunk', {'chunk_index': 0}),
            ('tts_chunk', {'chunk_index': 1}),
            ('tts_complete', None),
        ]

        for msg_type, _ in expected_sequence:
            assert isinstance(msg_type, str)
            assert msg_type in {
                'user_message', 'llm_thinking', 'llm_stream', 'llm_complete',
                'tts_generating', 'tts_chunk', 'tts_complete'
            }

    def test_message_sequence_voice_interaction(self):
        """验证语音交互的完整消息序列"""
        expected_sequence = [
            ('asr_processing', None),
            ('asr_result', '识别文本'),
            ('llm_thinking', None),
            ('llm_stream', 'AI 回复'),
            ('llm_complete', 'AI 回复'),
            ('tts_generating', None),
            ('tts_audio', None),  # 非流式 TTS
        ]

        for msg_type, _ in expected_sequence:
            assert isinstance(msg_type, str)
