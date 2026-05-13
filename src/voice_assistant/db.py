"""
共享数据库模块 - SQLite 对话历史存储
"""
import logging
import sqlite3
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

# 数据库路径
DB_PATH = Path(__file__).parent.parent.parent / "data" / "web_ui.db"
DB_PATH.parent.mkdir(exist_ok=True)


def get_db_path() -> Path:
    """获取数据库路径"""
    return DB_PATH


def init_db():
    """初始化数据库"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # 对话历史表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            title TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 消息表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT,
            role TEXT,
            content TEXT,
            audio_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id)
        )
    """)

    conn.commit()
    conn.close()
    logger.info(f"[DB] 数据库初始化完成: {DB_PATH}")


def save_message(conversation_id: str, role: str, content: str, audio_path: str | None = None):
    """保存消息到数据库"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO messages (conversation_id, role, content, audio_path) VALUES (?, ?, ?, ?)",
        (conversation_id, role, content, audio_path)
    )
    cursor.execute(
        "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (conversation_id,)
    )
    conn.commit()
    conn.close()


def create_conversation(title: str = None) -> str:
    """创建新对话"""
    conversation_id = str(uuid.uuid4())
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO conversations (id, title) VALUES (?, ?)",
        (conversation_id, title or "新对话")
    )
    conn.commit()
    conn.close()
    return conversation_id


def get_conversation_history(conversation_id: str, limit: int = 10) -> list:
    """获取对话历史（用于上下文）"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute(
        "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY created_at DESC LIMIT ?",
        (conversation_id, limit)
    )
    rows = cursor.fetchall()
    conn.close()
    return [{"role": r[0], "content": r[1]} for r in reversed(rows)]


def get_history(limit: int = 20) -> list:
    """获取对话历史列表"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, title, created_at FROM conversations ORDER BY updated_at DESC LIMIT ?",
        (limit,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [
        {"id": r[0], "title": r[1] or "新对话", "created_at": r[2]}
        for r in rows
    ]


def delete_conversation(conversation_id: str):
    """删除对话"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
    cursor.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
    conn.commit()
    conn.close()


def delete_conversations(conversation_ids: list[str]) -> int:
    """批量删除对话及其消息

    Args:
        conversation_ids: 要删除的对话 ID 列表

    Returns:
        删除的对话数量
    """
    if not conversation_ids:
        return 0

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    placeholders = ",".join("?" * len(conversation_ids))
    cursor.execute(
        f"DELETE FROM messages WHERE conversation_id IN ({placeholders})",
        conversation_ids,
    )
    cursor.execute(
        f"DELETE FROM conversations WHERE id IN ({placeholders})",
        conversation_ids,
    )
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted


def clear_history():
    """清空所有历史"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("DELETE FROM messages")
    cursor.execute("DELETE FROM conversations")
    conn.commit()
    conn.close()
