"""
ASR 纠错模块
使用 LLM 对语音识别结果进行语境纠错，优化中英文混合识别效果
"""
import logging
import re
from typing import Optional

from config import config

logger = logging.getLogger(__name__)

# 纠错系统提示词
CORRECTION_SYSTEM_PROMPT = """你是一个语音识别纠错助手。用户会提供一段语音识别的文本，其中可能包含识别错误的中英文混合内容。

你的任务是：
1. 识别可能的语音识别错误（尤其是英文技术术语被错误识别为中文发音）
2. 根据上下文语境纠正这些错误
3. 保持原文的语义和语气

常见纠错示例：
- "欧喷 因特普瑞特" → "Open Interpreter"
- "维埃斯 扣的" → "VS Code"
- "皮松" → "Python"
- "艾皮艾" → "API"
- "吉特" → "Git"
- "多克" → "Docker"

请直接输出纠错后的文本，不要解释。如果原文没有明显错误，直接返回原文。"""


def correct_asr_result(text: str, conversation_history: list = None) -> str:
    """对 ASR 识别结果进行纠错

    Args:
        text: ASR 识别的原始文本
        conversation_history: 对话历史，用于提供上下文

    Returns:
        纠错后的文本
    """
    # 如果文本很短或没有明显的识别错误特征，跳过纠错
    if len(text) < 3:
        return text

    # 检测是否需要纠错（包含可能的错误识别模式）
    if not _needs_correction(text):
        return text

    try:
        # 使用 LLM 进行纠错
        corrected = _llm_correct(text, conversation_history)
        if corrected and corrected != text:
            logger.info(f"ASR 纠错: '{text}' → '{corrected}'")
            return corrected
        return text
    except Exception as e:
        logger.warning(f"ASR 纠错失败: {e}")
        return text


def _needs_correction(text: str) -> bool:
    """检测文本是否需要纠错

    Args:
        text: 待检测文本

    Returns:
        是否需要纠错
    """
    # 如果文本包含英文，可能不需要纠错
    english_ratio = len(re.findall(r'[a-zA-Z]', text)) / max(len(text), 1)
    if english_ratio > 0.3:
        return False

    # 如果文本全是中文且没有明显的音译特征，可能不需要纠错
    # 但我们保守一点，对于技术相关的内容尝试纠错
    tech_keywords = [
        '打开', '运行', '执行', '启动', '关闭', '安装',
        '代码', '脚本', '程序', '文件', '终端', '命令'
    ]

    return any(kw in text for kw in tech_keywords)


def _llm_correct(text: str, conversation_history: list = None) -> Optional[str]:
    """使用 LLM 进行纠错

    Args:
        text: 待纠错文本
        conversation_history: 对话历史

    Returns:
        纠错后的文本
    """
    import requests

    llm_cfg = config.llm

    messages = [
        {"role": "system", "content": CORRECTION_SYSTEM_PROMPT}
    ]

    # 如果有对话历史，添加最近的上下文
    if conversation_history:
        recent = conversation_history[-3:]  # 最近 3 轮对话
        for msg in recent:
            messages.append(msg)

    messages.append({"role": "user", "content": text})

    try:
        response = requests.post(
            f"{llm_cfg.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {llm_cfg.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": llm_cfg.model,
                "messages": messages,
                "max_tokens": 500,
                "temperature": 0.1,  # 低温度，更确定性的输出
            },
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
            return content.strip() if content else text

        return text

    except Exception as e:
        logger.warning(f"LLM 纠错请求失败: {e}")
        return None


if __name__ == "__main__":
    # 测试纠错功能
    test_cases = [
        "帮我打开维埃斯扣的",
        "运行皮松脚本",
        "启动多克容器",
        "打开计算器",  # 不需要纠错
    ]

    print("ASR 纠错测试:")
    for text in test_cases:
        corrected = correct_asr_result(text)
        print(f"  '{text}' → '{corrected}'")