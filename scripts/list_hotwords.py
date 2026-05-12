"""列出已注册的热词（用于检查历史 vocabulary_id 是否可复用）"""
import os, sys
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
s = VocabularyService()
try:
    result = s.list_vocabularies(prefix="vasr", page_index=0, page_size=20)
    print("RESULT TYPE:", type(result).__name__)
    print("RESULT:", result)
except Exception as e:
    print(f"ERR {type(e).__name__}: {e}")
