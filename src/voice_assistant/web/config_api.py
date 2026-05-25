"""配置 API 路由"""
import logging

from fastapi import APIRouter, HTTPException

from voice_assistant.config import config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["config"])


@router.get("/config")
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
        },
        "history": {
            "max_turns": config.history.max_turns,
            "max_context_tokens": config.history.max_context_tokens,
        }
    }


@router.post("/config")
async def update_config(new_config: dict):
    """更新配置（运行时生效，不保存到文件）"""
    from voice_assistant.web.routes import validate_config

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

        if "history" in new_config:
            history_cfg = new_config["history"]
            if "max_turns" in history_cfg and history_cfg["max_turns"] is not None:
                config.history = config.history.__class__(
                    max_turns=int(history_cfg["max_turns"]),
                    max_context_tokens=config.history.max_context_tokens,
                )
            if "max_context_tokens" in history_cfg and history_cfg["max_context_tokens"] is not None:
                config.history = config.history.__class__(
                    max_turns=config.history.max_turns,
                    max_context_tokens=int(history_cfg["max_context_tokens"]),
                )

        logger.info(f"[WebUI] 配置已更新: {new_config}")
        return {"success": True}
    except Exception as e:
        logger.error(f"[WebUI] 配置更新失败: {e}")
        return {"success": False, "error": str(e)}


@router.get("/models")
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


@router.get("/ws-token")
async def get_ws_token(client_id: str):
    """为 WebSocket 连接生成认证令牌"""
    from voice_assistant.security.ws_auth import generate_token

    token = generate_token(client_id)
    return {"token": token, "ttl": 300}
