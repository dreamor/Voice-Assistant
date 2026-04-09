"""
AI Client 模块
使用 OpenRouter API 进行 AI 对话
"""
import json
import os
import re
import requests
from dotenv import load_dotenv

load_dotenv()

LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL")
LLM_MODEL = os.getenv("LLM_MODEL")
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT")


def ask_ai_stream(text, conversation_history=None):
    """使用流式API获取AI回复"""
    if conversation_history is None:
        conversation_history = []

    cleaned_text = re.sub(r'\s+', ' ', text).strip()

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]

    if conversation_history:
        messages.extend(conversation_history)

    messages.append({"role": "user", "content": cleaned_text})

    try:
        print("  [AI] Thinking...")

        response = requests.post(
            f"{LLM_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {LLM_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": LLM_MODEL,
                "messages": messages,
                "max_tokens": 500,
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

            if len(conversation_history) > 20:
                conversation_history[:] = conversation_history[-20:]
        else:
            yield "抱歉，没有得到有效回复。"

    except requests.Timeout:
        yield "抱歉，AI响应超时了。"
    except requests.ConnectionError:
        yield "抱歉，网络连接失败。"
    except Exception:
        yield "抱歉，发生错误。"
