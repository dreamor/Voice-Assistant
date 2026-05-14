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
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from collections import defaultdict

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from voice_assistant.config import config
from voice_assistant.core import VoiceSession
from voice_assistant.db import (
    init_db,
    save_message,
    create_conversation,
    get_conversation_history,
    get_history,
    delete_conversation,
    delete_conversations,
    clear_history,
    DB_PATH,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _convert_audio_to_wav(audio_bytes: bytes, audio_format: str = "audio/wav") -> bytes:
    """将音频数据转换为 WAV 格式（16kHz 单声道）

    支持 PCM 原始数据、WebM/OGG 等格式。
    PCM 数据直接包装为 WAV，其他格式使用 pydub 转换。
    转换失败时返回原始数据并记录警告。

    Args:
        audio_bytes: 原始音频字节数据
        audio_format: MIME 类型（如 audio/pcm, audio/webm, audio/ogg, audio/wav）

    Returns:
        WAV 格式音频字节数据（16kHz 单声道），或原始数据（转换失败时）
    """
    import io
    import struct
    import wave

    # PCM 格式：直接包装为 WAV
    if "pcm" in audio_format.lower():
        try:
            # 从 MIME 类型解析采样率，默认为 16000
            sample_rate = 16000
            if "rate=" in audio_format:
                try:
                    rate_str = audio_format.split("rate=")[1].split(";")[0].split(",")[0]
                    sample_rate = int(rate_str)
                except (ValueError, IndexError):
                    sample_rate = 16000

            # 创建 WAV 文件
            out = io.BytesIO()
            with wave.open(out, 'wb') as wav_file:
                wav_file.setnchannels(1)  # 单声道
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(audio_bytes)

            wav_data = out.getvalue()
            logger.info(f"[WebUI] PCM -> WAV 转换完成: {len(audio_bytes)} -> {len(wav_data)} bytes, 采样率: {sample_rate}")
            return wav_data
        except Exception as e:
            logger.error(f"[WebUI] PCM 转 WAV 失败: {e}")
            return audio_bytes

    # WAV 格式：尝试重采样到 16kHz 单声道
    if "wav" in audio_format.lower():
        try:
            import soundfile as sf
            buffer = io.BytesIO(audio_bytes)
            data, sr = sf.read(buffer)
            # 单声道
            if data.ndim > 1:
                data = data.mean(axis=1)
            # 重采样到 16kHz
            if sr != 16000:
                import numpy as np
                ratio = 16000 / sr
                n_samples = int(len(data) * ratio)
                data = np.interp(
                    np.linspace(0, len(data), n_samples),
                    np.arange(len(data)),
                    data,
                )
            out = io.BytesIO()
            sf.write(out, data, 16000, format="WAV")
            return out.getvalue()
        except Exception as e:
            logger.warning(f"[WebUI] WAV 重采样失败，使用原始数据: {e}")
            return audio_bytes

    # 非 WAV 格式（WebM/OGG 等）：使用 pydub 转换
    try:
        from pydub import AudioSegment

        # pydub 根据扩展名推断格式
        fmt = "webm" if "webm" in audio_format.lower() else "ogg"
        segment = AudioSegment.from_file(io.BytesIO(audio_bytes), format=fmt)
        # 转换为 16kHz 单声道
        segment = segment.set_frame_rate(16000).set_channels(1)
        out = io.BytesIO()
        segment.export(out, format="wav")
        logger.info(f"[WebUI] 音频转换完成: {fmt} -> WAV ({len(audio_bytes)} -> {out.tell()} bytes)")
        return out.getvalue()
    except ImportError:
        logger.error("[WebUI] pydub 未安装，无法转换音频格式。请运行: pip install pydub")
        return audio_bytes
    except Exception as e:
        logger.error(f"[WebUI] 音频转换失败 ({audio_format}): {e}")
        return audio_bytes


# 全局会话管理
sessions: dict[str, VoiceSession] = {}

# 待确认操作: client_id -> asyncio.Future
pending_confirms: dict[str, asyncio.Future] = {}


def get_or_create_session(client_id: str) -> VoiceSession:
    """获取或创建客户端会话"""
    if client_id not in sessions:
        session = VoiceSession(
            max_response_length=200,
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
    current_provider = config.providers.get_provider(config.provider) if config.provider else None
    base_url = current_provider.base_url if current_provider else None
    return {
        "llm": {
            "provider": config.provider,
            "model": config.llm.model,
            "base_url": base_url,
            "max_tokens": config.llm.max_tokens,
            "temperature": config.llm.temperature,
        },
        "asr": {
            "use_local": config.asr.use_local,
            "model": config.asr.model,
        },
        "audio": {
            "sample_rate": config.audio.sample_rate,
            "tts_voice": config.audio.tts.voice,
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
    """获取当前 provider 的可用模型列表（队首即主模型 = config.llm.model）"""
    provider = config.providers.get_provider(config.provider) if config.provider else None
    if provider is None:
        return {
            "models": [],
            "total": 0,
            "primary": config.llm.model,
            "provider": config.provider or "",
            "source": "none",
            "error": "未配置 provider，请在 ⚙ 配置页选择 Provider",
        }

    model_ids = [m.id for m in provider.models]
    primary = config.llm.model

    # 主模型提到队首（与 ModelManager fallback 顺序一致）
    if primary and primary in model_ids:
        ordered = [primary] + [m for m in model_ids if m != primary]
    else:
        ordered = model_ids

    return {
        "models": ordered,
        "total": len(ordered),
        "primary": primary,
        "provider": config.provider,
        "source": "provider",
    }


@app.get("/api/providers")
async def get_providers():
    """获取所有 Provider 及其模型列表"""
    providers_data = {}
    for pid, provider in config.providers.providers.items():
        providers_data[pid] = {
            "name": provider.name,
            "has_key": provider.has_key,
            "models": [{"id": m.id, "name": m.name} for m in provider.models],
            "is_custom": provider.is_custom,
            "base_url": provider.base_url,
        }

    return {
        "providers": providers_data,
        "current_provider": config.provider,
        "current_model": config.llm.model,
    }


@app.post("/api/providers/switch")
async def switch_provider(request: dict):
    """切换活跃 Provider 和模型，并把序号持久化到 .env 的 LLM_API_KEY"""
    from voice_assistant.core.model_manager import model_manager

    provider_id = request.get("provider_id", "")
    model_id = request.get("model_id")

    if not provider_id:
        raise HTTPException(status_code=400, detail="provider_id is required")

    result = model_manager.switch_provider(provider_id, model_id)
    if result is None:
        raise HTTPException(status_code=400, detail=f"无法切换到 Provider: {provider_id}")

    # 把 provider 的序号（从 1 开始）持久化到 .env
    provider_ids = list(config.providers.providers.keys())
    provider_index: int | None = None
    try:
        provider_index = provider_ids.index(provider_id) + 1
        _write_env_var("LLM_API_KEY", str(provider_index))
    except ValueError:
        logger.warning(f"[WebUI] provider {provider_id} 不在列表中，跳过 LLM_API_KEY 持久化")

    return {
        "success": True,
        "provider": provider_id,
        "provider_index": provider_index,
        "model": result.name,
    }


def _write_env_var(env_var: str, value: str) -> None:
    """把 KEY=VALUE 写入 .env，存在则覆盖该行"""
    env_path = Path(__file__).parent / ".env"
    lines = []
    found = False
    if env_path.exists():
        with open(env_path, encoding='utf-8') as f:
            for line in f:
                if line.startswith(f"{env_var}="):
                    lines.append(f"{env_var}={value}\n")
                    found = True
                else:
                    lines.append(line)
    if not found:
        lines.append(f"{env_var}={value}\n")
    with open(env_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    os.environ[env_var] = value


@app.post("/api/providers/api-key")
async def set_provider_api_key(request: dict):
    """设置 Provider 的 API Key（写入 .env 文件）"""
    provider_id = request.get("provider_id", "")
    api_key = request.get("api_key", "")

    if not provider_id or not api_key:
        raise HTTPException(status_code=400, detail="provider_id and api_key are required")

    provider = config.providers.get_provider(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail=f"Provider not found: {provider_id}")

    env_var = provider.api_key_env

    # 写入 .env 文件
    env_path = Path(__file__).parent / ".env"
    lines = []
    found = False

    if env_path.exists():
        with open(env_path, encoding='utf-8') as f:
            for line in f:
                if line.startswith(f"{env_var}="):
                    lines.append(f"{env_var}={api_key}\n")
                    found = True
                else:
                    lines.append(line)

    if not found:
        lines.append(f"{env_var}={api_key}\n")

    with open(env_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)

    # 立即更新环境变量
    os.environ[env_var] = api_key

    logger.info(f"[WebUI] API Key 已设置: {env_var}")
    return {"success": True, "env_var": env_var}


@app.post("/api/providers/create")
async def create_provider(request: dict):
    """创建自定义 Provider"""
    import re
    from voice_assistant.config import save_custom_provider

    provider_id = request.get("id", "").strip()
    name = request.get("name", "").strip()
    base_url = request.get("base_url", "").strip()
    api_key = request.get("api_key", "").strip()
    litellm_prefix = request.get("litellm_prefix", "openai")
    models = request.get("models", [])

    if not provider_id or not name or not base_url:
        raise HTTPException(status_code=400, detail="id, name, and base_url are required")

    if not re.match(r'^[a-zA-Z0-9_-]+$', provider_id):
        raise HTTPException(status_code=400, detail="Provider ID 只允许字母、数字、- 和 _")

    existing = config.providers.get_provider(provider_id)
    if existing and not existing.is_custom:
        raise HTTPException(status_code=400, detail=f"无法覆盖内置 Provider: {provider_id}")

    api_key_env = f"{provider_id.upper().replace('-', '_')}_API_KEY"

    try:
        provider = save_custom_provider(
            provider_id=provider_id,
            name=name,
            base_url=base_url,
            api_key_env=api_key_env,
            litellm_prefix=litellm_prefix,
            models=models,
        )

        # 保存 API Key 到 .env
        if api_key:
            env_path = Path(__file__).parent / ".env"
            lines = []
            found = False
            if env_path.exists():
                with open(env_path, encoding='utf-8') as f:
                    for line in f:
                        if line.startswith(f"{api_key_env}="):
                            lines.append(f"{api_key_env}={api_key}\n")
                            found = True
                        else:
                            lines.append(line)
            if not found:
                lines.append(f"{api_key_env}={api_key}\n")
            with open(env_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            os.environ[api_key_env] = api_key

        return {
            "success": True,
            "provider": {
                "id": provider_id,
                "name": provider.name,
                "has_key": provider.has_key or bool(api_key),
                "models": [{"id": m.id, "name": m.name} for m in provider.models],
                "is_custom": True,
                "base_url": provider.base_url,
            }
        }
    except Exception as e:
        logger.error(f"[WebUI] 创建 Provider 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/providers/{provider_id}")
async def delete_provider(provider_id: str):
    """删除自定义 Provider"""
    from voice_assistant.config import delete_custom_provider as do_delete

    provider = config.providers.get_provider(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail=f"Provider 不存在: {provider_id}")

    if not provider.is_custom:
        raise HTTPException(status_code=400, detail=f"无法删除内置 Provider: {provider_id}")

    if not do_delete(provider_id):
        raise HTTPException(status_code=500, detail="删除 Provider 失败")

    return {"success": True}


@app.patch("/api/providers/{provider_id}")
async def update_provider(provider_id: str, request: dict):
    """更新自定义 Provider（base_url / 模型列表 / 名称等）"""
    from voice_assistant.config import update_custom_provider

    provider = config.providers.get_provider(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail=f"Provider 不存在: {provider_id}")
    if not provider.is_custom:
        raise HTTPException(status_code=400, detail=f"无法修改内置 Provider: {provider_id}")

    updated = update_custom_provider(
        provider_id,
        name=request.get("name"),
        base_url=request.get("base_url"),
        litellm_prefix=request.get("litellm_prefix"),
        models=request.get("models"),
    )
    if updated is None:
        raise HTTPException(status_code=500, detail="更新失败")

    return {
        "success": True,
        "provider": {
            "id": provider_id,
            "name": updated.name,
            "has_key": updated.has_key,
            "models": [{"id": m.id, "name": m.name} for m in updated.models],
            "is_custom": True,
            "base_url": updated.base_url,
        },
    }


@app.get("/api/providers/{provider_id}/models")
async def fetch_provider_models(provider_id: str):
    """从 Provider 的 /models 端点自动获取模型列表"""
    import httpx

    provider = config.providers.get_provider(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail=f"Provider 不存在: {provider_id}")

    if not provider.base_url:
        raise HTTPException(status_code=400, detail=f"Provider {provider_id} 未配置 base_url")

    api_key = provider.api_key
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail=f"Provider {provider_id} 未配置 API Key（请先保存 Key 后再获取模型）",
        )

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            headers = {"Authorization": f"Bearer {api_key}"}
            url = f"{provider.base_url.rstrip('/')}/models"
            response = await client.get(url, headers=headers)
            response.raise_for_status()

            data = response.json()
            raw_models = data.get("data") or data.get("models") or []
            models = []
            for model in raw_models:
                if isinstance(model, dict):
                    model_id = model.get("id") or model.get("name") or ""
                    name = model.get("name") or model_id
                elif isinstance(model, str):
                    model_id = model
                    name = model
                else:
                    continue
                if model_id:
                    models.append({"id": model_id, "name": name})

            return {"models": models, "total": len(models)}
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="请求 Provider 超时（15s）")
    except httpx.HTTPStatusError as e:
        body = e.response.text[:200] if e.response is not None else ""
        raise HTTPException(
            status_code=502,
            detail=f"Provider /models 返回 {e.response.status_code}: {body}",
        )
    except Exception as e:
        logger.error(f"[WebUI] 获取 Provider 模型失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.get("/api/history")
async def get_history_endpoint(limit: int = 20):
    """获取对话历史列表"""
    history = get_history(limit=limit)
    return {"conversations": history}


@app.get("/api/history/{conversation_id}")
async def get_conversation(conversation_id: str):
    """获取单个对话详情"""
    import sqlite3
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
async def delete_conversation_endpoint(conversation_id: str):
    """删除对话"""
    delete_conversation(conversation_id)
    return {"success": True}


@app.post("/api/history/batch-delete")
async def batch_delete_conversations(request: dict):
    """批量删除对话"""
    ids = request.get("ids", [])
    if not ids:
        return {"deleted": 0}
    deleted = delete_conversations(ids)
    return {"deleted": deleted}


@app.post("/api/history/clear")
async def clear_history():
    """清空所有历史"""
    clear_history()
    return {"success": True}


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

                audio_base64 = data.get("base64Audio", "")

                # 获取音频格式
                audio_format = data.get("format", "audio/wav")

                # Debug: Save received data for diagnosis
                debug_ts = int(time.time() * 1000)
                try:
                    # 保存 base64 原文
                    with open(f'/tmp/debug_{client_id}_{debug_ts}.b64', 'w') as f:
                        f.write(audio_base64 if audio_base64 else "EMPTY")

                    audio_bytes = base64.b64decode(audio_base64)

                    # 保存解码后的原始 PCM 数据
                    with open(f'/tmp/debug_{client_id}_{debug_ts}.pcm', 'wb') as f:
                        f.write(audio_bytes)

                    logger.info(f"[DEBUG] 保存音频数据: /tmp/debug_{client_id}_{debug_ts}.pcm ({len(audio_bytes)} bytes)")
                except Exception as e:
                    logger.error(f"[DEBUG] 保存失败: {e}")

                try:
                    audio_bytes = base64.b64decode(audio_base64)
                    logger.info(f"[WebUI] 收到音频数据: {len(audio_bytes)} bytes, 格式: {audio_format}")
                except Exception as e:
                    logger.error(f"[WebUI] Base64 decode failed: {e}, base64 length: {len(audio_base64)}")
                    raise

                # 转换音频为 WAV 格式（16kHz 单声道）
                wav_bytes = _convert_audio_to_wav(audio_bytes, audio_format)

                # 语音识别
                await manager.send_message(client_id, {"type": "asr_processing"})

                try:
                    # 使用 VoiceSession 进行识别
                    session = get_or_create_session(client_id)
                    loop = asyncio.get_event_loop()
                    with ThreadPoolExecutor() as pool:
                        text = await loop.run_in_executor(pool, session.recognize, wav_bytes)

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

            elif msg_type == "confirm_response":
                # 用户确认/拒绝操作
                confirm_id = data.get("confirm_id", client_id)
                approved = data.get("approved", False)
                if confirm_id in pending_confirms:
                    future = pending_confirms.pop(confirm_id)
                    future.set_result(approved)
                else:
                    logger.warning(f"[WebUI] 收到未知确认响应: {confirm_id}")

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
    """处理 LLM 响应（流式优先，回退到同步）"""
    await manager.send_message(client_id, {"type": "llm_thinking"})

    try:
        # 获取会话
        session = get_or_create_session(client_id)

        # 获取对话历史
        history = get_conversation_history(conversation_id, limit=10)
        session.set_history(history)

        loop = asyncio.get_event_loop()

        # 定义确认回调
        def confirm_callback(tool_name: str, arguments: dict, guard_result) -> bool:
            """同步回调 — 通过 asyncio.Future 等待前端确认"""
            future = None
            confirm_id = None
            try:
                future = loop.create_future()
                confirm_id = f"{client_id}_{tool_name}_{id(future)}"
                pending_confirms[confirm_id] = future

                asyncio.run_coroutine_threadsafe(
                    manager.send_message(client_id, {
                        "type": "confirm_required",
                        "confirm_id": confirm_id,
                        "tool_name": tool_name,
                        "arguments": arguments,
                        "message": guard_result.message,
                        "level": guard_result.action.value,
                    }),
                    loop
                )

                timeout = config.agent.confirmation_timeout
                return future.result(timeout=timeout)
            except Exception as e:
                logger.error(f"[WebUI] 确认回调错误: {e}")
                return False
            finally:
                if confirm_id is not None:
                    pending_confirms.pop(confirm_id, None)

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

        session._on_execution_start = on_execution_start
        session._on_execution_end = on_execution_end
        session._confirm_callback = confirm_callback

        # 尝试流式处理
        full_response = ""
        use_stream = session._orchestrator is not None

        if use_stream:
            # 流式路径：在线程池中运行生成器
            import queue
            from voice_assistant.agent.orchestrator import AgentEvent

            event_queue: queue.Queue = queue.Queue()
            stream_error = [None]  # 用列表包装以便在闭包中修改

            def _run_stream():
                try:
                    for event in session.process_text_stream(user_text, history):
                        event_queue.put(event)
                except Exception as e:
                    stream_error[0] = e
                finally:
                    event_queue.put(None)  # 哨兵值

            with ThreadPoolExecutor() as pool:
                pool.submit(_run_stream)

                while True:
                    # 非阻塞地从队列取事件
                    try:
                        event = event_queue.get(timeout=0.05)
                    except queue.Empty:
                        await asyncio.sleep(0.01)
                        continue

                    if event is None:
                        break

                    if event.type == "llm_token":
                        full_response += (event.content or "")
                        await manager.send_message(client_id, {
                            "type": "llm_stream",
                            "content": event.content,
                        })

                    elif event.type == "tool_start":
                        await manager.send_message(client_id, {
                            "type": "executing",
                            "message": f"执行: {event.tool_name}",
                        })

                    elif event.type == "tool_result":
                        await manager.send_message(client_id, {
                            "type": "execution_complete",
                            "message": f"{event.tool_name}: {event.tool_result or '完成'}",
                        })

                    elif event.type == "complete":
                        process_result = event.result
                        if process_result and hasattr(process_result, 'response'):
                            full_response = process_result.response
                            if process_result.execution_output:
                                full_response = f"{full_response}\n\n执行结果:\n{process_result.execution_output}"

                    elif event.type == "error":
                        await manager.send_message(client_id, {
                            "type": "error",
                            "message": event.content or "处理失败",
                        })
                        return

                if stream_error[0]:
                    raise stream_error[0]

        else:
            # 同步回退路径
            with ThreadPoolExecutor() as pool:
                result = await asyncio.wait_for(
                    loop.run_in_executor(pool, session.process_text, user_text),
                    timeout=60.0
                )
            full_response = result.response
            if result.execution_output:
                full_response = f"{full_response}\n\n执行结果:\n{result.execution_output}"

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


async def generate_and_send_tts_stream(client_id: str, conversation_id: str, text: str):
    """流式生成并发送 TTS 音频（逐句推送）"""
    try:
        await manager.send_message(client_id, {"type": "tts_generating"})

        session = get_or_create_session(client_id)
        loop = asyncio.get_event_loop()

        chunk_index = 0
        with ThreadPoolExecutor() as pool:
            # 在线程池中运行流式合成生成器
            def stream_tts():
                return list(session.synthesize_stream(text))

            chunks = await loop.run_in_executor(pool, stream_tts)

        for chunk in chunks:
            if chunk:
                audio_b64 = base64.b64encode(chunk).decode("utf-8")
                await manager.send_message(client_id, {
                    "type": "tts_chunk",
                    "data": audio_b64,
                    "format": "mp3",
                    "chunk_index": chunk_index
                })
                chunk_index += 1
                # 小延迟避免前端拥塞
                await asyncio.sleep(0.05)

        # 发送完成标记
        await manager.send_message(client_id, {"type": "tts_complete"})

    except Exception as e:
        logger.error(f"[WebUI] 流式TTS错误: {e}")
        # 回退到普通TTS
        await generate_and_send_tts(client_id, conversation_id, text)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
