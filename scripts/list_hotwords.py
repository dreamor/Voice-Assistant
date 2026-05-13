# ruff: noqa: E402
"""列出账号下已注册的热词列表，并与本地 hotwords.json 做匹配对比。

用法：
    python scripts/list_hotwords.py             # 仅列出
    python scripts/list_hotwords.py --match     # 同时与本地 hotwords.json 匹配，标注最优 ID
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

import dashscope

dashscope.api_key = (
    os.environ.get("DASHSCOPE_API_KEY")
    or os.environ.get("ASR_API_KEY")
    or os.environ.get("LLM_API_KEY")
)

from dashscope.audio.asr import VocabularyService

PREFIX = os.environ.get("HOTWORDS_PREFIX", "vasr")


def main() -> int:
    do_match = "--match" in sys.argv

    service = VocabularyService()
    items = service.list_vocabularies(prefix=PREFIX, page_index=0, page_size=50)
    print(f"[INFO] 账号下 {PREFIX} 前缀热词列表共 {len(items)} 个\n")

    if not do_match:
        for it in items:
            print(f"  {it['vocabulary_id']:50s}  {it.get('gmt_create')}  {it.get('status')}")
        return 0

    hot_file = ROOT / "config" / "hotwords.json"
    if not hot_file.exists():
        print(f"[ERROR] 未找到 {hot_file}")
        return 1
    with open(hot_file, encoding="utf-8") as f:
        target = {w["text"] for w in json.load(f).get("vocabulary", [])}
    print(f"[INFO] 本地 hotwords.json: {len(target)} 词\n")

    best_id, best_score = None, -1
    for it in items:
        vid = it["vocabulary_id"]
        try:
            v = service.query_vocabulary(vid)
        except Exception as e:
            print(f"  [SKIP] {vid}: {e}")
            continue
        vocab = v.get("vocabulary", []) if isinstance(v, dict) else v
        words = {w.get("text") for w in vocab} if isinstance(vocab, list) else set()
        score = len(target & words)
        print(f"  {vid:50s}  size={len(words):3d}  overlap={score}/{len(target)}")
        if score > best_score:
            best_score, best_id = score, vid

    if best_id:
        print()
        print("================================================")
        print(f"  BEST vocabulary_id = {best_id}")
        print(f"  overlap: {best_score}/{len(target)}")
        print("================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
