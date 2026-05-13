#!/usr/bin/env python3
# ruff: noqa: E402
"""注册热词到 DashScope，并打印 vocabulary_id。

用法：
    source .venv/bin/activate
    python scripts/register_hotwords.py

将打印的 vocabulary_id 填入 config.yaml 的 asr.hotwords.vocabulary_id，
并将 asr.hotwords.enabled 设为 true 即可启用热词识别。

可选环境变量：
    HOTWORDS_FILE         热词 JSON 文件（默认 config/hotwords.json）
    HOTWORDS_TARGET_MODEL ASR 模型（默认 paraformer-realtime-v2）
    HOTWORDS_PREFIX       热词列表前缀（默认 vasr）
"""
import json
import os
import sys
from pathlib import Path

# 让脚本在仓库根目录下可直接运行
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")


def main() -> int:
    api_key = (
        os.environ.get("DASHSCOPE_API_KEY")
        or os.environ.get("ASR_API_KEY")
        or os.environ.get("LLM_API_KEY")
    )
    if not api_key:
        print("[ERROR] 未找到 DASHSCOPE_API_KEY / ASR_API_KEY / LLM_API_KEY，请先在 .env 配置")
        return 1

    hotwords_file = Path(os.environ.get("HOTWORDS_FILE", ROOT / "config" / "hotwords.json"))
    if not hotwords_file.exists():
        print(f"[ERROR] 热词文件不存在: {hotwords_file}")
        return 1

    with open(hotwords_file, encoding="utf-8") as f:
        data = json.load(f)
    vocabulary = data.get("vocabulary", [])
    if not vocabulary:
        print("[ERROR] 热词文件 vocabulary 数组为空")
        return 1

    target_model = os.environ.get("HOTWORDS_TARGET_MODEL", "paraformer-realtime-v2")
    prefix = os.environ.get("HOTWORDS_PREFIX", "vasr")

    print(f"[INFO] 从 {hotwords_file} 加载 {len(vocabulary)} 个热词")
    print(f"[INFO] target_model={target_model}  prefix={prefix}")

    import dashscope
    dashscope.api_key = api_key

    from dashscope.audio.asr import VocabularyService

    service = VocabularyService()
    try:
        vocabulary_id = service.create_vocabulary(
            target_model=target_model,
            prefix=prefix,
            vocabulary=vocabulary,
        )
    except Exception as e:
        msg = str(e)
        if "429" in msg or "Throttling" in msg or "quota" in msg.lower():
            print(f"[ERROR] 配额已用完（免费限额，请升级付费套餐）: {e}")
        else:
            print(f"[ERROR] 创建热词失败: {type(e).__name__}: {e}")
        return 2

    if not vocabulary_id:
        print("[ERROR] 创建成功但返回的 vocabulary_id 为空")
        return 3

    print()
    print("================================================")
    print(f"  vocabulary_id = {vocabulary_id}")
    print("================================================")
    print()
    print("下一步：编辑 config.yaml")
    print("  asr.hotwords.enabled: true")
    print(f"  asr.hotwords.vocabulary_id: \"{vocabulary_id}\"")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
