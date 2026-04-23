"""
Voice Assistant Web UI
本地语音助手 Web 界面

启动命令:
    python web_ui.py
    或
    python -m voice_assistant --web

功能:
- 录音输入（浏览器原生）
- 实时语音识别（ASR）
- LLM 流式对话
- TTS 语音播放
- 设置配置
- 对话历史
"""
import asyncio
import base64
import json
import logging
import os
import sqlite3
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional
from collections import defaultdict

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from voice_assistant.config import config
from voice_assistant.core import VoiceSession

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 数据库路径
DB_PATH = Path(__file__).parent / "data" / "web_ui.db"
DB_PATH.parent.mkdir(exist_ok=True)


def init_db():
    """初始化数据库"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # 对话历史表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            title TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 消息表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT,
            role TEXT,
            content TEXT,
            audio_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id)
        )
    """)

    conn.commit()
    conn.close()
    logger.info(f"[WebUI] 数据库初始化完成: {DB_PATH}")


# 全局会话管理
sessions: dict[str, VoiceSession] = {}


def get_or_create_session(client_id: str) -> VoiceSession:
    """获取或创建客户端会话"""
    if client_id not in sessions:
        session = VoiceSession(
            auto_mode=True,
            max_response_length=200,
            execution_timeout=60.0,
            on_intent_detected=lambda intent, conf: logger.info(f"[{client_id}] Intent: {intent} ({conf})"),
        )
        session.initialize()
        sessions[client_id] = session
        logger.info(f"[WebUI] 创建新会话: {client_id}")
    return sessions[client_id]


def cleanup_session(client_id: str):
    """清理客户端会话"""
    if client_id in sessions:
        sessions[client_id].cleanup()
        del sessions[client_id]
        logger.info(f"[WebUI] 清理会话: {client_id}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    init_db()
    logger.info("[WebUI] 服务启动")
    yield
    # 清理所有会话
    for client_id in list(sessions.keys()):
        cleanup_session(client_id)
    logger.info("[WebUI] 服务关闭")


app = FastAPI(
    title="Voice Assistant Web UI",
    description="语音助手 Web 界面",
    version="2.2.0",
    lifespan=lifespan
)

# 静态文件服务
app.mount("/static", StaticFiles(directory="web_static"), name="static")


@app.get("/")
async def root():
    """主页"""
    return FileResponse("web_static/index.html")


@app.get("/favicon.ico")
async def favicon():
    """favicon"""
    return FileResponse("web_static/favicon.ico")


@app.get("/api/config")
async def get_config():
    """获取当前配置"""
    return {
        "llm": {
            "model": config.llm.model,
            "base_url": config.llm.base_url,
            "max_tokens": config.llm.max_tokens,
            "temperature": config.llm.temperature,
        },
        "asr": {
            "use_local": config.asr.use_local,
            "model": config.asr.model,
        },
        "audio": {
            "sample_rate": config.audio.sample_rate,
            "edge_tts_voice": config.audio.edge_tts_voice,
        }
    }


@app.post("/api/config")
async def update_config(new_config: dict):
    """更新配置（运行时生效，不保存到文件）"""
    # 输入验证
    valid, error_msg = validate_config(new_config)
    if not valid:
        raise HTTPException(status_code=400, detail=error_msg)

    try:
        if "llm" in new_config:
            llm_cfg = new_config["llm"]
            if "model" in llm_cfg and llm_cfg["model"]:
                config.llm.model = str(llm_cfg["model"])
            if "max_tokens" in llm_cfg and llm_cfg["max_tokens"] is not None:
                config.llm.max_tokens = int(llm_cfg["max_tokens"])
            if "temperature" in llm_cfg and llm_cfg["temperature"] is not None:
                config.llm.temperature = float(llm_cfg["temperature"])

        if "audio" in new_config:
            audio_cfg = new_config["audio"]
            if "edge_tts_voice" in audio_cfg and audio_cfg["edge_tts_voice"]:
                config.audio.edge_tts_voice = str(audio_cfg["edge_tts_voice"])

        # ASR 配置暂时不支持运行时修改（因为 ASRConfig 是 frozen 的）
        # 如果需要修改 asr.use_local，需要重启服务

        logger.info(f"[WebUI] 配置已更新: {new_config}")
        return {"success": True}
    except Exception as e:
        logger.error(f"[WebUI] 配置更新失败: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/models")
async def get_models():
    """获取可用模型列表（从配置文件读取）"""
    try:
        model_names = config.llm_models.get_model_names()
        primary_model = config.llm.model

        return {
            "models": model_names,
            "total": len(model_names),
            "primary": primary_model,
            "checked": False,  # 不再运行时检查
            "source": "config"
        }
    except Exception as e:
        logger.error(f"[WebUI] 获取模型列表失败: {e}")
        # 回退到默认模型列表
        default_models = [
            "qwen-plus-latest", "qwen-turbo-latest", "qwen-max-latest",
            "deepseek-v3.1", "deepseek-v3",
        ]
        return {
            "models": default_models,
            "total": len(default_models),
            "primary": config.llm.model,
            "checked": False,
            "source": "fallback",
            "error": str(e)
        }


@app.get("/api/history")
async def get_history(limit: int = 20):
    """获取对话历史列表"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, title, created_at FROM conversations ORDER BY updated_at DESC LIMIT ?",
        (limit,)
    )
    rows = cursor.fetchall()
    conn.close()

    return {
        "conversations": [
            {"id": r[0], "title": r[1] or "新对话", "created_at": r[2]}
            for r in rows
        ]
    }


@app.get("/api/history/{conversation_id}")
async def get_conversation(conversation_id: str):
    """获取单个对话详情"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, title, created_at FROM conversations WHERE id = ?",
        (conversation_id,)
    )
    conv = cursor.fetchone()

    if not conv:
        conn.close()
        return {"error": "对话不存在"}

    cursor.execute(
        "SELECT role, content, created_at FROM messages WHERE conversation_id = ? ORDER BY created_at",
        (conversation_id,)
    )
    messages = cursor.fetchall()
    conn.close()

    return {
        "id": conv[0],
        "title": conv[1],
        "created_at": conv[2],
        "messages": [
            {"role": m[0], "content": m[1], "created_at": m[2]}
            for m in messages
        ]
    }


@app.delete("/api/history/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """删除对话"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
    cursor.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
    conn.commit()
    conn.close()
    return {"success": True}


@app.post("/api/history/clear")
async def clear_history():
    """清空所有历史"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("DELETE FROM messages")
    cursor.execute("DELETE FROM conversations")
    conn.commit()
    conn.close()
    return {"success": True}


def save_message(conversation_id: str, role: str, content: str, audio_path: Optional[str] = None):
    """保存消息到数据库"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO messages (conversation_id, role, content, audio_path) VALUES (?, ?, ?, ?)",
        (conversation_id, role, content, audio_path)
    )
    cursor.execute(
        "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (conversation_id,)
    )
    conn.commit()
    conn.close()


def create_conversation(title: str = None) -> str:
    """创建新对话"""
    conversation_id = str(uuid.uuid4())
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO conversations (id, title) VALUES (?, ?)",
        (conversation_id, title or "新对话")
    )
    conn.commit()
    conn.close()
    return conversation_id


def get_conversation_history(conversation_id: str, limit: int = 10) -> list:
    """获取对话历史（用于上下文）"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute(
        "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY created_at DESC LIMIT ?",
        (conversation_id, limit)
    )
    rows = cursor.fetchall()
    conn.close()
    return [{"role": r[0], "content": r[1]} for r in reversed(rows)]


class ConnectionManager:
    """WebSocket 连接管理"""
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"[WebUI] 客户端连接: {client_id}")

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(f"[WebUI] 客户端断开: {client_id}")

    async def send_message(self, client_id: str, message: dict):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_json(message)


manager = ConnectionManager()


class RateLimiter:
    """简单的速率限制器"""

    def __init__(self, max_requests: int = 30, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: dict[str, list[float]] = defaultdict(list)

    def check(self, client_id: str) -> bool:
        """检查是否超过限制"""
        now = time.time()
        # 清理过期记录
        self.requests[client_id] = [
            t for t in self.requests[client_id]
            if now - t < self.window_seconds
        ]

        if len(self.requests[client_id]) >= self.max_requests:
            return False

        self.requests[client_id].append(now)
        return True


# 速率限制器实例
rate_limiter = RateLimiter(max_requests=30, window_seconds=60)


# 配置验证 schema
VALID_LLM_MODELS = [
    "kimi-k2.5", "qwen-turbo", "qwen-plus", "qwen-max",
    "qwen-long", "llama3.1-8b-instruct", "qwen2.5-7b-instruct"
]

VALID_TTS_VOICES = [
    "zh-CN-XiaoxiaoNeural", "zh-CN-YunxiNeural", "zh-CN-YunyangNeural",
    "zh-CN-XiaoyiNeural", "zh-CN-YunjieNeural"
]

def validate_config(new_config: dict) -> tuple[bool, str]:
    """验证配置输入"""
    if "llm" in new_config:
        llm = new_config["llm"]
        # 模型名称不做严格验证，由 API 层面处理
        if "temperature" in llm:
            temp = llm["temperature"]
            if not isinstance(temp, (int, float)) or temp < 0 or temp > 2:
                return False, "temperature 必须在 0-2 之间"
        if "max_tokens" in llm:
            tokens = llm["max_tokens"]
            if not isinstance(tokens, int) or tokens < 1 or tokens > 10000:
                return False, "max_tokens 必须在 1-10000 之间"

    if "audio" in new_config:
        audio = new_config["audio"]
        # TTS 音色不做严格验证，由 edge-tts 处理

    if "asr" in new_config:
        asr = new_config["asr"]
        if "use_local" in asr and not isinstance(asr["use_local"], bool):
            return False, "use_local 必须是布尔值"

    return True, ""


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket 端点 - 处理实时通信"""
    # 速率限制检查
    if not rate_limiter.check(client_id):
        await websocket.send_json({
            "type": "error",
            "message": "请求过于频繁，请稍后再试"
        })
        await websocket.close()
        return

    await manager.connect(websocket, client_id)
    conversation_id = None

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "start_conversation":
                # 开始新对话
                title = data.get("title", "新对话")
                conversation_id = create_conversation(title)
                await manager.send_message(client_id, {
                    "type": "conversation_started",
                    "conversation_id": conversation_id
                })

            elif msg_type == "load_conversation":
                # 加载已有对话
                conversation_id = data.get("conversation_id")
                await manager.send_message(client_id, {
                    "type": "conversation_loaded",
                    "conversation_id": conversation_id
                })

            elif msg_type == "audio_data":
                # 处理音频数据
                if not conversation_id:
                    conversation_id = create_conversation()

                audio_base64 = data.get("data", "")
                audio_bytes = base64.b64decode(audio_base64)

                # 获取音频格式
                audio_format = data.get("format", "audio/wav")
                logger.info(f"[WebUI] 收到音频数据: {len(audio_bytes)} bytes, 格式: {audio_format}")

                # 根据格式保存临时文件
                if "webm" in audio_format or "ogg" in audio_format:
                    temp_input = f"/tmp/va_audio_{client_id}.webm"
                    temp_wav = f"/tmp/va_audio_{client_id}_converted.wav"
                else:
                    temp_input = f"/tmp/va_audio_{client_id}.wav"
                    temp_wav = temp_input

                with open(temp_input, "wb") as f:
                    f.write(audio_bytes)

                # 如果不是 wav 格式，转换为 wav
                final_audio_path = temp_input
                if temp_input != temp_wav:
                    try:
                        import subprocess
                        subprocess.run([
                            'ffmpeg', '-i', temp_input, '-ar', '16000', '-ac', '1',
                            '-y', temp_wav
                        ], check=True, capture_output=True)
                        final_audio_path = temp_wav
                        logger.info(f"[WebUI] 音频转换完成: {temp_wav}")
                    except Exception as e:
                        logger.error(f"[WebUI] 音频转换失败: {e}")
                        # 转换失败时尝试直接使用原文件
                        final_audio_path = temp_input

                # 语音识别
                await manager.send_message(client_id, {"type": "asr_processing"})

                try:
                    # 读取音频文件
                    with open(final_audio_path, 'rb') as f:
                        audio_data = f.read()

                    # 使用 VoiceSession 进行识别
                    session = get_or_create_session(client_id)
                    loop = asyncio.get_event_loop()
                    with ThreadPoolExecutor() as pool:
                        text = await loop.run_in_executor(pool, session.recognize, audio_data)

                    if text:
                        # 发送识别结果
                        await manager.send_message(client_id, {
                            "type": "asr_result",
                            "content": text
                        })
                    else:
                        await manager.send_message(client_id, {
                            "type": "error",
                            "message": "未能识别语音，请重试"
                        })

                except Exception as e:
                    logger.error(f"[WebUI] ASR 错误: {e}")
                    await manager.send_message(client_id, {
                        "type": "error",
                        "message": f"语音识别失败: {str(e)}"
                    })

                # 清理临时文件
                if os.path.exists(temp_input):
                    os.remove(temp_input)
                if temp_input != temp_wav and os.path.exists(temp_wav):
                    os.remove(temp_wav)

            elif msg_type == "text_message":
                # 处理文本消息
                if not conversation_id:
                    conversation_id = create_conversation()

                text = data.get("content", "").strip()
                if text:
                    save_message(conversation_id, "user", text)
                    await process_llm_response(client_id, conversation_id, text)

            elif msg_type == "ping":
                await manager.send_message(client_id, {"type": "pong"})

            elif msg_type == "replay_tts":
                # 处理 TTS 重播请求
                text = data.get("content", "")
                if text:
                    await manager.send_message(client_id, {"type": "tts_generating"})
                    try:
                        session = get_or_create_session(client_id)
                        loop = asyncio.get_event_loop()
                        with ThreadPoolExecutor() as pool:
                            audio_data = await loop.run_in_executor(pool, session.synthesize, text)

                        if audio_data:
                            audio_b64 = base64.b64encode(audio_data).decode("utf-8")
                            await manager.send_message(client_id, {
                                "type": "tts_audio",
                                "data": audio_b64,
                                "format": "mp3"
                            })
                        else:
                            await manager.send_message(client_id, {
                                "type": "error",
                                "message": "语音合成失败"
                            })
                    except Exception as e:
                        logger.error(f"[WebUI] TTS 重播错误: {e}")
                        await manager.send_message(client_id, {
                            "type": "error",
                            "message": f"语音合成失败: {str(e)}"
                        })

    except WebSocketDisconnect:
        manager.disconnect(client_id)
        cleanup_session(client_id)
    except Exception as e:
        logger.error(f"[WebUI] WebSocket 错误: {e}")
        manager.disconnect(client_id)
        cleanup_session(client_id)


async def process_llm_response(client_id: str, conversation_id: str, user_text: str):
    """处理 LLM 响应（使用 VoiceSession）"""
    await manager.send_message(client_id, {"type": "llm_thinking"})

    try:
        # 获取会话
        session = get_or_create_session(client_id)
        
        # 获取对话历史
        history = get_conversation_history(conversation_id, limit=10)
        session.set_history(history)

        # 处理文本
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as pool:
            # 定义回调的同步包装
            def on_execution_start():
                asyncio.run_coroutine_threadsafe(
                    manager.send_message(client_id, {
                        "type": "executing",
                        "message": "正在执行操作..."
                    }),
                    loop
                )
            
            def on_execution_end():
                asyncio.run_coroutine_threadsafe(
                    manager.send_message(client_id, {
                        "type": "execution_complete",
                        "message": "操作执行完成"
                    }),
                    loop
                )
            
            # 临时设置回调
            session._on_execution_start = on_execution_start
            session._on_execution_end = on_execution_end
            
            result = await asyncio.wait_for(
                loop.run_in_executor(pool, session.process_text, user_text),
                timeout=60.0
            )

        full_response = result.response

        # 如果有执行结果
        if result.execution_output:
            full_response = f"{full_response}\n\n执行结果:\n{result.execution_output}"

        # 发送完整响应
        await manager.send_message(client_id, {
            "type": "llm_stream",
            "content": full_response
        })

        # 发送完成标记
        await manager.send_message(client_id, {
            "type": "llm_complete",
            "content": full_response
        })

        # 保存 AI 响应
        save_message(conversation_id, "assistant", full_response)

        # 生成 TTS 音频
        await generate_and_send_tts(client_id, conversation_id, full_response)

    except asyncio.TimeoutError:
        logger.error(f"[WebUI] 处理超时（60秒）")
        await manager.send_message(client_id, {
            "type": "error",
            "message": "处理超时，请重试或尝试更简单的操作"
        })
    except Exception as e:
        logger.error(f"[WebUI] 处理错误: {e}")
        await manager.send_message(client_id, {
            "type": "error",
            "message": f"处理请求失败: {str(e)}"
        })


async def generate_and_send_tts(client_id: str, conversation_id: str, text: str):
    """生成并发送 TTS 音频（使用 VoiceSession）"""
    try:
        await manager.send_message(client_id, {"type": "tts_generating"})

        session = get_or_create_session(client_id)
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as pool:
            audio_data = await loop.run_in_executor(pool, session.synthesize, text)

        if audio_data:
            audio_b64 = base64.b64encode(audio_data).decode("utf-8")
            await manager.send_message(client_id, {
                "type": "tts_audio",
                "data": audio_b64,
                "format": "mp3"
            })
        else:
            logger.warning("[WebUI] TTS 生成失败")

    except Exception as e:
        logger.error(f"[WebUI] TTS 错误: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
