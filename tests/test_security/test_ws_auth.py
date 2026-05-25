"""WebSocket 认证模块测试"""
from voice_assistant.security.ws_auth import (
    TOKEN_TTL,
    generate_token,
    is_auth_required,
    verify_token,
)


class TestGenerateAndVerifyToken:
    def test_valid_token(self):
        token = generate_token("client-1")
        assert verify_token(token, "client-1")

    def test_token_wrong_client_id(self):
        token = generate_token("client-1")
        assert not verify_token(token, "client-2")

    def test_token_expired(self):
        # 生成令牌后篡改时间戳使其过期
        token = generate_token("client-1")
        ts_str, _sig = token.split(".", 1)
        # 使用过期时间戳 + 重新签名无法匹配密钥，直接用过期时间戳构造
        # 更简单的方式：直接验证过期时间戳
        from voice_assistant.security import ws_auth

        old_time = ws_auth.time.time
        try:
            ws_auth.time.time = lambda: int(ts_str) + TOKEN_TTL + 1
            assert not verify_token(token, "client-1")
        finally:
            ws_auth.time.time = old_time

    def test_empty_token(self):
        assert not verify_token("", "client-1")

    def test_malformed_token(self):
        assert not verify_token("no-dot", "client-1")
        assert not verify_token("abc.def.ghi", "client-1")

    def test_invalid_timestamp(self):
        assert not verify_token("notanumber.somesig", "client-1")

    def test_wrong_signature(self):
        token = generate_token("client-1")
        ts, _ = token.split(".", 1)
        assert not verify_token(f"{ts}.badsignature", "client-1")


class TestIsAuthRequired:
    def test_localhost_no_auth(self):
        assert not is_auth_required("127.0.0.1")
        assert not is_auth_required("::1")
        assert not is_auth_required("localhost")

    def test_remote_requires_auth(self):
        assert is_auth_required("192.168.1.100")
        assert is_auth_required("10.0.0.1")

    def test_none_host_requires_auth(self):
        # 未知来源默认需要认证
        assert is_auth_required(None)

    def test_auth_enabled_overrides(self):
        import os

        original = os.environ.get("WS_AUTH_ENABLED")
        try:
            os.environ["WS_AUTH_ENABLED"] = "true"
            # 重新加载模块级变量
            import importlib

            from voice_assistant.security import ws_auth

            importlib.reload(ws_auth)
            assert ws_auth.is_auth_required("127.0.0.1")
        finally:
            if original is None:
                os.environ.pop("WS_AUTH_ENABLED", None)
            else:
                os.environ["WS_AUTH_ENABLED"] = original
            importlib.reload(ws_auth)
