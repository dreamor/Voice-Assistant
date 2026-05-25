"""Provider 管理 API 路由"""
import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException

from voice_assistant.config import config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/providers", tags=["providers"])


def _write_env_var(env_var: str, value: str) -> None:
    """把 KEY=VALUE 写入 .env，存在则覆盖该行"""
    env_path = Path(__file__).parent.parent.parent.parent / ".env"
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


@router.get("")
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


@router.post("/switch")
async def switch_provider(request: dict):
    """切换活跃 Provider 和模型"""
    from voice_assistant.core.model_manager import model_manager

    provider_id = request.get("provider_id", "")
    model_id = request.get("model_id")

    if not provider_id:
        raise HTTPException(status_code=400, detail="provider_id is required")

    result = model_manager.switch_provider(provider_id, model_id)
    if result is None:
        raise HTTPException(status_code=400, detail=f"无法切换到 Provider: {provider_id}")

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


@router.post("/api-key")
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
    env_path = Path(__file__).parent.parent.parent.parent / ".env"
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

    os.environ[env_var] = api_key
    logger.info(f"[WebUI] API Key 已设置: {env_var}")
    return {"success": True, "env_var": env_var}


@router.post("/create")
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

        if api_key:
            env_path = Path(__file__).parent.parent.parent.parent / ".env"
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


@router.delete("/{provider_id}")
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


@router.patch("/{provider_id}")
async def update_provider(provider_id: str, request: dict):
    """更新自定义 Provider"""
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


@router.get("/{provider_id}/models")
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
