"""
Voice Assistant 入口
默认启动 Web UI 服务
"""
import sys


def main():
    """主入口 - 启动 Web UI"""
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        from voice_assistant.core.dependencies import validate_environment
        result = validate_environment()
        sys.exit(0 if result else 1)
    else:
        import uvicorn
        from pathlib import Path
        project_root = str(Path(__file__).resolve().parent.parent.parent)
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        print("[Web] Starting Voice Assistant Web UI...")
        print("[Web] Visit: http://127.0.0.1:8000")
        uvicorn.run("web_ui:app", host="127.0.0.1", port=8000, log_level="info")


if __name__ == "__main__":
    main()