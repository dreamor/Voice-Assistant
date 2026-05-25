"""历史记录 API 路由"""
import sqlite3

from fastapi import APIRouter

from voice_assistant.db import (
    DB_PATH,
    clear_history,
    delete_conversation,
    delete_conversations,
    get_history,
)

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("")
async def get_history_endpoint(limit: int = 20):
    """获取对话历史列表"""
    history = get_history(limit=limit)
    return {"conversations": history}


@router.get("/{conversation_id}")
async def get_conversation(conversation_id: str):
    """获取单个对话详情"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, title, created_at FROM conversations WHERE id = ?",
        (conversation_id,)
    )
    conv = cursor.fetchone()

    if not conv:
        conn.close()
        return {"error": "对话不存在"}

    cursor.execute(
        "SELECT role, content, created_at FROM messages WHERE conversation_id = ? ORDER BY created_at",
        (conversation_id,)
    )
    messages = cursor.fetchall()
    conn.close()

    return {
        "id": conv[0],
        "title": conv[1],
        "created_at": conv[2],
        "messages": [
            {"role": m[0], "content": m[1], "created_at": m[2]}
            for m in messages
        ]
    }


@router.delete("/{conversation_id}")
async def delete_conversation_endpoint(conversation_id: str):
    """删除对话"""
    delete_conversation(conversation_id)
    return {"success": True}


@router.post("/batch-delete")
async def batch_delete_conversations(request: dict):
    """批量删除对话"""
    ids = request.get("ids", [])
    if not ids:
        return {"deleted": 0}
    deleted = delete_conversations(ids)
    return {"deleted": deleted}


@router.post("/clear")
async def clear_history_endpoint():
    """清空所有历史"""
    clear_history()
    return {"success": True}
