"""历史记录 API 路由"""
import sqlite3

from fastapi import APIRouter

from voice_assistant.db import (
    DB_PATH,
    clear_history,
    delete_conversation,
    delete_conversations,
    get_conversation_tree,
    get_history,
    save_message_with_tree,
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


@router.get("/{conversation_id}/tree")
async def get_tree(conversation_id: str):
    """获取对话的树结构"""
    nodes = get_conversation_tree(conversation_id)
    return {"conversation_id": conversation_id, "nodes": nodes}


@router.post("/{conversation_id}/branch")
async def create_branch(conversation_id: str, request: dict):
    """从指定消息创建分支

    Body: {"parent_node_id": "...", "role": "user", "content": "..."}
    """
    parent_node_id = request.get("parent_node_id")
    role = request.get("role", "user")
    content = request.get("content", "")

    if not parent_node_id:
        return {"error": "parent_node_id 必填"}

    node_id = save_message_with_tree(
        conversation_id=conversation_id,
        role=role,
        content=content,
        parent_id=parent_node_id,
    )
    return {"success": True, "node_id": node_id, "parent_node_id": parent_node_id}


@router.put("/{conversation_id}/active")
async def switch_active(conversation_id: str, request: dict):
    """切换活跃分支

    Body: {"leaf_node_id": "..."}
    """
    leaf_node_id = request.get("leaf_node_id")
    if not leaf_node_id:
        return {"error": "leaf_node_id 必填"}

    # 验证节点存在
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM messages WHERE conversation_id = ? AND node_id = ?",
        (conversation_id, leaf_node_id),
    )
    if not cursor.fetchone():
        conn.close()
        return {"error": "节点不存在"}

    conn.close()
    return {"success": True, "active_leaf_id": leaf_node_id}
