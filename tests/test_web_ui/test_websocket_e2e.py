"""WebSocket 端到端冒烟测试

使用 FastAPI TestClient 测试 WebSocket 端点的基本消息收发。
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app_client():
    """提供 TestClient，禁用 WS 认证"""
    import web_ui as web_ui_mod

    with patch("voice_assistant.web.ws.is_auth_required", return_value=False):
        with TestClient(web_ui_mod.app) as client:
            yield client


class TestWebSocketPingPong:
    """测试 ping/pong 基本通信"""

    def test_ping_returns_pong(self, app_client):
        with app_client.websocket_connect("/ws/test-ping") as ws:
            ws.send_json({"type": "ping"})
            data = ws.receive_json()
            assert data["type"] == "pong"


class TestWebSocketTextMessage:
    """测试 text_message 流程（mock LLM）"""

    @patch("voice_assistant.web.ws.generate_and_send_tts", new_callable=lambda: lambda: MagicMock())
    @patch("voice_assistant.web.ws.get_or_create_session")
    @patch("voice_assistant.web.ws.get_conversation_history", return_value=[])
    @patch("voice_assistant.web.ws.save_message")
    def test_text_message_sends_llm_thinking(
        self, mock_save, mock_history, mock_session, mock_tts, app_client
    ):
        from voice_assistant.core.session import ProcessResult

        mock_sess = MagicMock()
        mock_sess._orchestrator = MagicMock()
        mock_sess._history = []
        mock_sess._confirm_callback = None
        mock_sess._on_execution_start = None
        mock_sess._on_execution_end = None
        mock_sess.process_text.return_value = ProcessResult(
            response="你好！",
            intent_type="agent",
            confidence=1.0,
        )
        mock_sess.synthesize.return_value = None
        mock_session.return_value = mock_sess

        with app_client.websocket_connect("/ws/test-text") as ws:
            ws.send_json({"type": "start_conversation", "title": "test"})
            started = ws.receive_json()
            assert started["type"] == "conversation_started"

            ws.send_json({"type": "text_message", "content": "你好"})

            msg = ws.receive_json()
            assert msg["type"] == "llm_thinking"

            # Consume remaining messages until llm_complete or error
            while True:
                msg = ws.receive_json()
                if msg["type"] in ("llm_complete", "error"):
                    break


class TestWebSocketConversation:
    """测试会话管理"""

    def test_start_conversation(self, app_client):
        with app_client.websocket_connect("/ws/test-conv") as ws:
            ws.send_json({"type": "start_conversation", "title": "测试对话"})
            data = ws.receive_json()
            assert data["type"] == "conversation_started"
            assert "conversation_id" in data

    def test_load_conversation(self, app_client):
        with app_client.websocket_connect("/ws/test-load") as ws:
            ws.send_json({"type": "load_conversation", "conversation_id": "test-123"})
            data = ws.receive_json()
            assert data["type"] == "conversation_loaded"
            assert data["conversation_id"] == "test-123"


class TestWebSocketConfirmResponse:
    """测试确认响应流程"""

    def test_confirm_response_unknown_id(self, app_client):
        """未知的 confirm_id 应该被忽略（不崩溃）"""
        with app_client.websocket_connect("/ws/test-confirm") as ws:
            ws.send_json({
                "type": "confirm_response",
                "confirm_id": "nonexistent_id",
                "approved": True,
            })
            ws.send_json({"type": "ping"})
            data = ws.receive_json()
            assert data["type"] == "pong"


class TestWebSocketSessionManagement:
    """测试会话创建和清理"""

    def test_multiple_connections_different_clients(self, app_client):
        """不同 client_id 应创建不同会话"""
        with app_client.websocket_connect("/ws/client-a") as ws_a:
            with app_client.websocket_connect("/ws/client-b") as ws_b:
                ws_a.send_json({"type": "ping"})
                ws_b.send_json({"type": "ping"})

                data_a = ws_a.receive_json()
                data_b = ws_b.receive_json()

                assert data_a["type"] == "pong"
                assert data_b["type"] == "pong"
