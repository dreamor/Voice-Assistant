"""platform 模块单元测试"""
import pytest
import platform as stdlib_platform
from voice_assistant.platform import (
    PlatformAdapter, MacAdapter, WindowsAdapter,
    detect_platform, create_adapter, get_adapter, get_platform,
)


class TestDetectPlatform:
    def test_returns_known_platform(self):
        result = detect_platform()
        assert result in ("mac", "windows", "linux")

    def test_macos_detected_as_mac(self):
        if stdlib_platform.system() == "Darwin":
            assert detect_platform() == "mac"

    def test_windows_detected(self):
        if stdlib_platform.system() == "Windows":
            assert detect_platform() == "windows"


class TestMacAdapter:
    @pytest.fixture
    def adapter(self):
        if stdlib_platform.system() != "Darwin":
            pytest.skip("macOS only")
        return MacAdapter()

    def test_open_url(self, adapter):
        result = adapter.open_url("https://example.com")
        assert "打开" in result or "open" in result.lower()

    def test_run_script_echo(self, adapter):
        code, stdout, stderr = adapter.run_script('display dialog "test"', shell=None)
        assert isinstance(code, int)


class TestWindowsAdapter:
    @pytest.fixture
    def adapter(self):
        if stdlib_platform.system() != "Windows":
            pytest.skip("Windows only")
        return WindowsAdapter()

    def test_open_url(self, adapter):
        result = adapter.open_url("https://example.com")
        assert isinstance(result, str)


class TestCreateAdapter:
    def test_creates_correct_type(self):
        adapter = create_adapter()
        system = stdlib_platform.system()
        if system == "Darwin":
            assert isinstance(adapter, MacAdapter)
        elif system == "Windows":
            assert isinstance(adapter, WindowsAdapter)

    def test_linux_raises(self):
        if stdlib_platform.system() == "Linux":
            with pytest.raises(RuntimeError):
                create_adapter()


class TestGetAdapter:
    def test_singleton(self):
        a1 = get_adapter()
        a2 = get_adapter()
        assert a1 is a2


class TestGetPlatform:
    def test_returns_string(self):
        assert isinstance(get_platform(), str)