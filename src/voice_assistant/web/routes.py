"""静态路由与配置验证"""
import logging
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["static"])

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
        if "temperature" in llm:
            temp = llm["temperature"]
            if not isinstance(temp, (int, float)) or temp < 0 or temp > 2:
                return False, "temperature 必须在 0-2 之间"
        if "max_tokens" in llm:
            tokens = llm["max_tokens"]
            if not isinstance(tokens, int) or tokens < 1 or tokens > 10000:
                return False, "max_tokens 必须在 1-10000 之间"

    if "audio" in new_config:
        pass

    if "asr" in new_config:
        asr = new_config["asr"]
        if "use_local" in asr and not isinstance(asr["use_local"], bool):
            return False, "use_local 必须是布尔值"

    if "history" in new_config:
        history = new_config["history"]
        if "max_turns" in history:
            mt = history["max_turns"]
            if not isinstance(mt, int) or mt < 1:
                return False, "history.max_turns 必须 >= 1"
        if "max_context_tokens" in history:
            mct = history["max_context_tokens"]
            if not isinstance(mct, int) or mct < 500:
                return False, "history.max_context_tokens 必须 >= 500"

    return True, ""


STATIC_DIR = Path(__file__).parent.parent.parent.parent / "web_static"


@router.get("/")
async def root():
    """主页"""
    return FileResponse(str(STATIC_DIR / "index.html"))


@router.get("/favicon.ico")
async def favicon():
    """favicon"""
    return FileResponse(str(STATIC_DIR / "favicon.ico"))
