"""
Voice Assistant 命令行入口
支持: python -m voice_assistant [--check] [--web]
"""
import sys


def main():
    """主入口"""
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        # 环境检查模式
        from scripts.check_env import main as check_main
        sys.exit(check_main())
    elif len(sys.argv) > 1 and sys.argv[1] == "--web":
        # Web UI 模式
        import uvicorn
        from web_ui import app
        print("[Web] Starting Voice Assistant Web UI...")
        print("[Web] Visit: http://127.0.0.1:8000")
        uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
    else:
        # 正常启动
        from voice_assistant.main import main as app_main
        app_main()


if __name__ == "__main__":
    main()