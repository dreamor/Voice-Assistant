"""
Voice Assistant 命令行入口
支持: python -m voice_assistant [--check]
"""
import sys


def main():
    """主入口"""
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        # 环境检查模式
        from scripts.check_env import main as check_main
        sys.exit(check_main())
    else:
        # 正常启动
        from voice_assistant.main import main as app_main
        app_main()


if __name__ == "__main__":
    main()