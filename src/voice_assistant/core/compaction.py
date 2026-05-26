"""上下文压缩 — 当 token 逼近上限时，用 LLM 对旧消息生成结构化摘要"""
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

DEFAULT_MAX_CONTEXT_TOKENS = 6000
DEFAULT_RESERVE_TOKENS = 2000
DEFAULT_KEEP_RECENT_TOKENS = 1500

COMPACT_PROMPT = """请将以下对话历史压缩为简洁的结构化摘要，保留：
1. 用户的关键偏好和需求
2. 已执行的重要操作及其结果
3. 未完成的任务或待确认的事项
4. 任何需要后续参考的上下文

忽略闲聊和重复内容。用中文输出。

对话历史：
{messages}"""


@dataclass
class CompactionResult:
    """压缩结果"""
    summary: str
    messages_removed: int
    messages_kept: int
    tokens_before: int
    tokens_after: int


def estimate_tokens(messages: list[dict]) -> int:
    """粗略估算消息列表的 token 数。

    中文约 1.5 字符/token，英文约 4 字符/token。
    每条消息额外计入 4 token 的角色/格式开销。
    """
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        if content is None:
            content = ""
        zh_chars = sum(1 for c in content if "一" <= c <= "鿿")
        other_chars = len(content) - zh_chars
        total += int(zh_chars / 1.5) + int(other_chars / 4) + 4
    return total


def should_compact(
    messages: list[dict],
    max_context_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS,
    reserve_tokens: int = DEFAULT_RESERVE_TOKENS,
) -> bool:
    """检查是否需要压缩"""
    return estimate_tokens(messages) > max_context_tokens - reserve_tokens


def _call_llm_for_summary(prompt: str) -> str:
    """调用 LLM 生成摘要（轻量调用）"""
    try:
        import litellm

        from voice_assistant.config import config

        model = getattr(config.llm, "model", "gpt-4o-mini")
        response = litellm.completion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
            temperature=0.1,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"[Compactor] LLM 摘要生成失败: {e}")
        return ""


def _format_messages_for_compact(messages: list[dict]) -> str:
    """将消息列表格式化为摘要 prompt 的文本"""
    lines = []
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        if content is None:
            content = ""
        if role == "system":
            continue
        lines.append(f"[{role}] {content[:300]}")
    return "\n".join(lines)


def _emit_compact_event(name: str, data: dict) -> None:
    """通过 EventBus 发送压缩事件（通知用途，不可拦截）"""
    try:
        from voice_assistant.core.events import Event, EventName, get_event_bus
        bus = get_event_bus()
        event_name = EventName(name) if name in EventName.__members__ else name
        bus.emit(Event(name=event_name, data=data))
    except Exception:
        pass


def compact(
    messages: list[dict],
    max_context_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS,
    keep_recent_tokens: int = DEFAULT_KEEP_RECENT_TOKENS,
) -> CompactionResult:
    """执行上下文压缩。

    保留最近 keep_recent_tokens 的消息，对旧消息生成摘要后替换。
    """
    tokens_before = estimate_tokens(messages)
    if tokens_before <= max_context_tokens - DEFAULT_RESERVE_TOKENS:
        return CompactionResult(
            summary="",
            messages_removed=0,
            messages_kept=len(messages),
            tokens_before=tokens_before,
            tokens_after=tokens_before,
        )

    # 从最新消息开始，保留最近 keep_recent_tokens 的消息
    recent_messages: list[dict] = []
    recent_tokens = 0
    for msg in reversed(messages):
        msg_tokens = estimate_tokens([msg])
        if recent_tokens + msg_tokens > keep_recent_tokens:
            break
        recent_messages.insert(0, msg)
        recent_tokens += msg_tokens

    # 旧消息 = 原始消息中不在 recent 中的部分
    recent_ids = {id(m) for m in recent_messages}
    old_messages = [m for m in messages if id(m) not in recent_ids]

    if not old_messages:
        return CompactionResult(
            summary="",
            messages_removed=0,
            messages_kept=len(messages),
            tokens_before=tokens_before,
            tokens_after=tokens_before,
        )

    # 生成摘要
    formatted = _format_messages_for_compact(old_messages)
    prompt = COMPACT_PROMPT.format(messages=formatted)

    _emit_compact_event("compact_start", {
        "messages_total": len(messages),
        "messages_old": len(old_messages),
        "tokens_before": tokens_before,
    })

    summary = _call_llm_for_summary(prompt)

    if not summary:
        # LLM 失败，降级为简单裁剪
        logger.warning("[Compactor] LLM 摘要失败，降级为简单裁剪")
        summary = "[历史摘要生成失败，已裁剪旧消息]"

    # 构建压缩后的消息列表
    compact_messages = [
        {"role": "system", "content": f"[上下文摘要]\n{summary}"},
    ] + recent_messages

    tokens_after = estimate_tokens(compact_messages)
    logger.info(
        f"[Compactor] 压缩完成: {len(messages)} → {len(compact_messages)} 条消息, "
        f"{tokens_before} → {tokens_after} tokens (移除 {len(old_messages)} 条)"
    )

    _emit_compact_event("compact_end", {
        "messages_removed": len(old_messages),
        "messages_kept": len(compact_messages),
        "tokens_before": tokens_before,
        "tokens_after": tokens_after,
        "llm_success": bool(summary and not summary.startswith("[历史摘要生成失败")),
    })

    return CompactionResult(
        summary=summary,
        messages_removed=len(old_messages),
        messages_kept=len(compact_messages),
        tokens_before=tokens_before,
        tokens_after=tokens_after,
    )
