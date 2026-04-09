"""
AI Client 模块
使用 LLM API 进行 AI 对话
"""
import json
import re
import requests
from config import config


# 默认系统提示词
DEFAULT_SYSTEM_PROMPT = "你是一个友好的中文语音助手，回复要简洁口语化，适合语音播放。"


def ask_ai_stream(text, conversation_history=None):
    """使用流式API获取AI回复"""
    if conversation_history is None:
        conversation_history = []

    llm_cfg = config.llm
    cleaned_text = re.sub(r'\s+', ' ', text).strip()

    messages = [
        {"role": "system", "content": DEFAULT_SYSTEM_PROMPT}
    ]

    if conversation_history:
        messages.extend(conversation_history)

    messages.append({"role": "user", "content": cleaned_text})

    try:
        print("  [AI] Thinking...")

        response = requests.post(
            f"{llm_cfg.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {llm_cfg.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": llm_cfg.model,
                "messages": messages,
                "max_tokens": llm_cfg.max_tokens,
                "temperature": llm_cfg.temperature,
                "stream": True,
            },
            stream=True,
            timeout=120
        )

        if response.status_code != 200:
            yield f"抱歉，AI服务暂时不可用 ({response.status_code})。"
            return

        full_content = []

        for line in response.iter_lines():
            if not line:
                continue

            line = line.decode('utf-8', errors='replace')
            if not line.startswith('data: '):
                continue

            data_str = line[6:]
            if data_str == '[DONE]':
                break

            try:
                data = json.loads(data_str)
            except:
                continue

            delta = data.get('choices', [{}])[0].get('delta', {})
            content = delta.get('content', '') or delta.get('reasoning', '')

            if content:
                full_content.append(content)
                yield ''.join(full_content)

        final_content = ''.join(full_content)

        if final_content:
            conversation_history.append({"role": "user", "content": cleaned_text})
            conversation_history.append({"role": "assistant", "content": final_content})

            max_turns = config.history.max_turns
            if len(conversation_history) > max_turns:
                conversation_history[:] = conversation_history[-max_turns:]
        else:
            yield "抱歉，没有得到有效回复。"

    except requests.Timeout:
        yield "抱歉，AI响应超时了。"
    except requests.ConnectionError:
        yield "抱歉，网络连接失败。"
    except Exception:
        yield "抱歉，发生错误。"