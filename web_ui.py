"""
Voice Assistant Web UI - 入口脚本

启动命令:
    python web_ui.py
    或
    python -m voice_assistant --web
"""
from voice_assistant.web import create_app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
