"""选最匹配当前 hotwords.json 的已存在 vocabulary，并打印其 ID。"""
import json, os, sys
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

with open(ROOT / "config" / "hotwords.json", encoding="utf-8") as f:
    target = {w["text"] for w in json.load(f).get("vocabulary", [])}

print(f"[INFO] target hotwords count: {len(target)}")

s = VocabularyService()
items = s.list_vocabularies(prefix="vasr", page_index=0, page_size=50)
best_id, best_score = None, -1
for item in items:
    vid = item["vocabulary_id"]
    try:
        v = s.query_vocabulary(vid)
    except Exception as e:
        print(f"  [SKIP] {vid}: {e}")
        continue
    # v 可能是 list 或 dict
    if hasattr(v, 'output'):
        vocab = v.output
    elif isinstance(v, dict) and 'vocabulary' in v:
        vocab = v['vocabulary']
    else:
        vocab = v
    if isinstance(vocab, dict) and 'vocabulary' in vocab:
        vocab = vocab['vocabulary']
    words = {w.get("text") for w in vocab} if isinstance(vocab, list) else set()
    score = len(target & words)
    print(f"  {vid[:40]:40s}  size={len(words):3d}  overlap={score}")
    if score > best_score:
        best_score, best_id, best_size = score, vid, len(words)

print()
print("================================================")
print(f"  BEST vocabulary_id = {best_id}")
print(f"  overlap with current hotwords.json: {best_score}/{len(target)}")
print("================================================")
