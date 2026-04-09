"""
语音助手 - Open Interpreter 版本
功能: 麦克风收音 → STT → LLM执行 → 语音反馈
"""
import os
import io
import soundfile as sf
import subprocess

from dotenv import load_dotenv

load_dotenv()

SAMPLE_RATE = int(os.getenv("SAMPLE_RATE"))
ASR_MODEL = os.getenv("ASR_MODEL")

from vad import record_audio
from ai_client import ask_ai_stream
from tts import synthesize
from audio_player import play_audio
from cloud_asr import CloudASR

ASR_API_KEY = os.getenv("ASR_API_KEY")

conversation_history = []

LLM_MODEL = os.getenv("LLM_MODEL")
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL")


def call_llm(prompt: str, system_prompt: str = None) -> str:
    """直接使用 OpenAI 客户端调用阿里云百炼"""
    from openai import OpenAI
    
    client = OpenAI(
        api_key=LLM_API_KEY,
        base_url=LLM_BASE_URL
    )
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            max_tokens=2000,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"调用失败: {e}"


def execute_code(code: str, language: str = "python") -> str:
    """执行代码"""
    if language.lower() == "python":
        try:
            result = subprocess.run(
                ["python", "-c", code],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                return result.stdout if result.stdout else "执行完成"
            else:
                return f"错误: {result.stderr}"
        except Exception as e:
            return f"执行失败: {e}"
    elif language.lower() in ["bash", "shell", "cmd"]:
        try:
            result = subprocess.run(
                code,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                return result.stdout if result.stdout else "执行完成"
            else:
                return f"错误: {result.stderr}"
        except Exception as e:
            return f"执行失败: {e}"
    else:
        return f"不支持的语言: {language}"


def handle_with_interpreter(user_text: str) -> str:
    """使用 LLM + 代码执行 处理"""
    
    # 判断是否是电脑操作相关
    computer_keywords = ["打开", "关闭", "创建", "删除", "截屏", "截图", "新建", "运行", "执行", 
                         "打开文件", "关闭窗口", "启动", "停止", "复制", "移动", "重命名",
                         "搜索", "查找", "下载", "上传", "安装", "卸载", "控制", "操作"]
    
    is_computer_task = any(keyword in user_text for keyword in computer_keywords)
    
    if is_computer_task:
        # 电脑操作 - 精简回复
        system_prompt = """你是一个命令行助手，可以用Python代码控制电脑执行各种操作。

当用户要求你操作电脑时：
1. 只执行简单的文件操作和系统命令（如打开应用、创建文件、截屏等）
2. 如果需要执行代码，写出Python代码并执行
3. 用简洁的语言回复，不需要解释代码细节

重要：不要执行危险操作。"""

        response = call_llm(user_text, system_prompt)
        
        # 检查是否包含代码块
        if "```python" in response or "```" in response:
            import re
            code_match = re.search(r'```(?:python)?\n(.*?)```', response, re.DOTALL)
            if code_match:
                code = code_match.group(1).strip()
                print(f"  [Executing] {code[:80]}...")
                exec_result = execute_code(code)
                
                # 输出详细执行结果到控制台
                print(f"  [Result] {exec_result[:200]}")
                
                if "错误" in exec_result or "失败" in exec_result:
                    return f"执行失败"
                else:
                    return "任务完成"
        
        # 没有执行代码，只返回精简结果
        print(f"  [Response] {response[:100]}")
        return "任务完成"
    else:
        # 普通聊天 - 详细回复
        system_prompt = "你是一个友好的语音助手，直接用自然语言回答用户问题。回答要简洁、口语化，适合语音播放。"
        response = call_llm(user_text, system_prompt)
        
        # 限制长度，避免TTS太长
        if len(response) > 200:
            response = response[:200] + "..."
        
        return response


def recognize(audio_bytes):
    """语音识别（使用阿里云ASR）"""
    try:
        asr = CloudASR(api_key=ASR_API_KEY, model=ASR_MODEL)
        result = asr.recognize_from_bytes(audio_bytes)

        if result and not result.startswith("云端ASR错误"):
            return result
        else:
            print(f"  [Error] Cloud ASR failed: {result}")
            return ""
    except Exception as e:
        print(f"  [Error] Cloud ASR error: {e}")
        return ""


def handle_with_ai(user_text: str) -> str:
    """使用 AI 对话"""
    print("  [AI] Using AI chat")
    reply = ""
    for partial in ask_ai_stream(user_text, conversation_history):
        reply = partial
        print(partial, end='', flush=True)
    print()
    return reply


def speak_and_play(text: str):
    """语音合成并播放"""
    if not text:
        return
    print(f"\n[Speaking] {text}")
    audio_data = synthesize(text)
    print(f"  [OK] {len(audio_data)} bytes")
    print("[Playing]")
    play_audio(audio_data)


def main():
    print("\n" + "=" * 50)
    print("  AI Voice Assistant (Open Interpreter)")
    print("=" * 50)
    print(f"  ASR: {ASR_MODEL}")
    print(f"  LLM: {LLM_MODEL}")
    print("=" * 50)
    print("  [ENTER] Start recording")
    print("  [C]     Clear history")
    print("  [H]     Show history")
    print("  [I]     Toggle Interpreter/AI")
    print("  [Q]     Quit")
    print("=" * 50)
    print("\nReady!\n")

    use_interpreter = True

    while True:
        mode = "Interpreter" if use_interpreter else "AI"
        cmd = input(f"[ENTER=Record / C=Clear / H=History / I=Toggle / Q=Quit] (模式:{mode}): ").strip().lower()

        if cmd == 'q':
            print("Bye!")
            break
        elif cmd == 'c':
            conversation_history.clear()
            print("[OK] History cleared\n")
            continue
        elif cmd == 'h':
            if conversation_history:
                print("\n--- History ---")
                for i in range(0, len(conversation_history), 2):
                    if i + 1 < len(conversation_history):
                        print(f"\n[Q] {conversation_history[i]['content']}")
                        print(f"[A] {conversation_history[i+1]['content']}")
                print("\n--- End ---\n")
            else:
                print("[Info] No history\n")
            continue
        elif cmd == 'i':
            use_interpreter = not use_interpreter
            print(f"[OK] Switched to {mode}\n")
            continue

        print("\n[Recording] Speak now...")
        audio = record_audio(max_seconds=30)

        if len(audio) < SAMPLE_RATE * 0.5:
            print("[Warning] Too short\n")
            continue

        print(f"  [OK] Recorded {len(audio)/SAMPLE_RATE:.1f}s")

        print("\n[Step 1] Recognizing...")
        with io.BytesIO() as buf:
            sf.write(buf, audio, SAMPLE_RATE, format='WAV')
            audio_bytes = buf.getvalue()

        user_text = recognize(audio_bytes)
        print(f"  You: {user_text}")

        if not user_text.strip():
            print("[Warning] No speech detected\n")
            continue

        print("\n[Step 2] Processing...")
        if use_interpreter:
            reply = handle_with_interpreter(user_text)
        else:
            reply = handle_with_ai(user_text)
        print(f"  Reply: {reply[:200]}...")

        print("\n[Step 3] Speaking...")
        speak_and_play(reply)
        print("\n" + "-" * 50 + "\n")


if __name__ == "__main__":
    main()