# ruff: noqa: E402
"""清理多余的热词列表，保留正在使用的一个。

策略：
- 保留 config.yaml 中配置的 vocabulary_id
- 删除其他所有 vasr 前缀的 vocabulary
- 默认 dry-run，加 --apply 真正执行
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

import yaml

with open(ROOT / "config.yaml", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)
keep_id = cfg.get("asr", {}).get("hotwords", {}).get("vocabulary_id")
if not keep_id:
    print("[ERROR] config.yaml 未配置 asr.hotwords.vocabulary_id，停止清理避免误删")
    sys.exit(1)

apply = "--apply" in sys.argv

import dashscope

dashscope.api_key = (
    os.environ.get("DASHSCOPE_API_KEY")
    or os.environ.get("ASR_API_KEY")
    or os.environ.get("LLM_API_KEY")
)

from dashscope.audio.asr import VocabularyService

s = VocabularyService()

items = s.list_vocabularies(prefix="vasr", page_index=0, page_size=50)
print(f"[INFO] 账号下 vasr 前缀热词列表共 {len(items)} 个")
print(f"[INFO] 保留: {keep_id}")
print()

to_delete = [it for it in items if it["vocabulary_id"] != keep_id]
print(f"[INFO] 将删除 {len(to_delete)} 个：")
for it in to_delete:
    print(f"  - {it['vocabulary_id']}  ({it.get('gmt_create')})")

if not apply:
    print()
    print("[DRY-RUN] 加 --apply 真正执行删除")
    sys.exit(0)

print()
deleted = 0
for it in to_delete:
    vid = it["vocabulary_id"]
    try:
        s.delete_vocabulary(vid)
        print(f"  [OK] {vid}")
        deleted += 1
    except Exception as e:
        print(f"  [FAIL] {vid}: {e}")

remaining = s.list_vocabularies(prefix="vasr", page_index=0, page_size=50)
print()
print(f"[DONE] 删除 {deleted} 个，剩余 {len(remaining)} 个：")
for it in remaining:
    print(f"  - {it['vocabulary_id']}")
