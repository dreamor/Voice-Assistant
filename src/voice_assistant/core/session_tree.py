"""SessionTree — 树形会话结构

支持分支、切换、摘要。每条消息有 id + parent_id，
可以从任意节点创建分支，切换活跃分支。
"""
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TreeNode:
    """树节点 — 对应一条消息"""

    id: str
    parent_id: str | None
    role: str  # user / assistant / system / tool
    content: str
    timestamp: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "parent_id": self.parent_id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    def to_message(self) -> dict[str, str]:
        """导出为 LLM 消息格式"""
        return {"role": self.role, "content": self.content}


class SessionTree:
    """树形会话结构

    用法:
        tree = SessionTree()
        node_id = tree.append("user", "你好")
        tree.append("assistant", "你好！有什么可以帮你的？")
        branch_id = tree.branch(node_id)
        tree.switch_branch(branch_id)
        tree.append("user", "换一种回答")
    """

    def __init__(self) -> None:
        self._nodes: dict[str, TreeNode] = {}
        self._children: dict[str, list[str]] = {}  # parent_id -> [child_ids]
        self._active_leaf_id: str | None = None
        self._root_id: str | None = None

    @property
    def active_leaf_id(self) -> str | None:
        return self._active_leaf_id

    @property
    def root_id(self) -> str | None:
        return self._root_id

    def append(
        self,
        role: str,
        content: str,
        parent_id: str | None = None,
        **metadata: Any,
    ) -> str:
        """追加消息，返回 node_id。

        Args:
            role: 消息角色 (user/assistant/system/tool)
            content: 消息内容
            parent_id: 父节点 ID。None 追加到当前活跃叶子。
            **metadata: 额外元数据
        """
        import time

        node_id = str(uuid.uuid4())
        actual_parent = parent_id

        if actual_parent is None:
            actual_parent = self._active_leaf_id

        node = TreeNode(
            id=node_id,
            parent_id=actual_parent,
            role=role,
            content=content,
            timestamp=time.time(),
            metadata=metadata,
        )
        self._nodes[node_id] = node

        if actual_parent is not None:
            self._children.setdefault(actual_parent, []).append(node_id)
        else:
            self._root_id = node_id

        self._active_leaf_id = node_id
        return node_id

    def branch(self, from_node_id: str, role: str = "user", content: str = "", **metadata: Any) -> str:
        """从指定节点创建新分支，返回新节点的 node_id。

        Args:
            from_node_id: 分支起点（新节点的父节点）
            role: 新消息角色
            content: 新消息内容
            **metadata: 额外元数据
        """
        if from_node_id not in self._nodes:
            raise ValueError(f"节点不存在: {from_node_id}")

        node_id = self.append(role, content, parent_id=from_node_id, **metadata)
        return node_id

    def get_node(self, node_id: str) -> TreeNode | None:
        """获取指定节点"""
        return self._nodes.get(node_id)

    def get_active_branch(self) -> list[TreeNode]:
        """获取从 root 到 active_leaf 的完整路径"""
        if self._active_leaf_id is None:
            return []

        path: list[TreeNode] = []
        current_id = self._active_leaf_id
        while current_id is not None:
            node = self._nodes.get(current_id)
            if node is None:
                break
            path.append(node)
            current_id = node.parent_id

        path.reverse()
        return path

    def switch_branch(self, leaf_id: str) -> None:
        """切换活跃分支到指定叶子节点"""
        if leaf_id not in self._nodes:
            raise ValueError(f"节点不存在: {leaf_id}")
        self._active_leaf_id = leaf_id

    def list_branches(self, node_id: str) -> list[list[TreeNode]]:
        """列出某个节点的所有子分支（每个分支是从 node_id 到叶子的路径）"""
        if node_id not in self._nodes:
            return []

        children = self._children.get(node_id, [])
        branches: list[list[TreeNode]] = []

        for child_id in children:
            # DFS 找到所有叶子
            leaves = self._find_leaves(child_id)
            for leaf_id in leaves:
                path = self._path_between(node_id, leaf_id)
                if path:
                    branches.append(path)

        return branches

    def to_messages(self) -> list[dict[str, str]]:
        """将活跃分支导出为 LLM 消息列表格式"""
        return [node.to_message() for node in self.get_active_branch()]

    def from_messages(self, messages: list[dict[str, str]]) -> None:
        """从扁平消息列表构建树（用于兼容旧数据）"""
        self._nodes.clear()
        self._children.clear()
        self._active_leaf_id = None
        self._root_id = None

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if content is None:
                content = ""
            self.append(role, content)

    def node_count(self) -> int:
        return len(self._nodes)

    def _find_leaves(self, node_id: str) -> list[str]:
        """找到从 node_id 可达的所有叶子节点"""
        children = self._children.get(node_id, [])
        if not children:
            return [node_id]
        leaves: list[str] = []
        for child_id in children:
            leaves.extend(self._find_leaves(child_id))
        return leaves

    def _path_between(self, from_id: str, to_id: str) -> list[TreeNode]:
        """获取从 from_id 到 to_id 的路径（from_id 不包含在内）"""
        path: list[TreeNode] = []
        current_id = to_id
        while current_id is not None and current_id != from_id:
            node = self._nodes.get(current_id)
            if node is None:
                return []
            path.append(node)
            current_id = node.parent_id

        if current_id != from_id:
            return []

        path.reverse()
        return path

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典（用于持久化）"""
        return {
            "nodes": {nid: n.to_dict() for nid, n in self._nodes.items()},
            "active_leaf_id": self._active_leaf_id,
            "root_id": self._root_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SessionTree":
        """从字典反序列化"""
        tree = cls()
        for nid, ndata in data.get("nodes", {}).items():
            node = TreeNode(
                id=ndata["id"],
                parent_id=ndata.get("parent_id"),
                role=ndata["role"],
                content=ndata["content"],
                timestamp=ndata.get("timestamp", 0),
                metadata=ndata.get("metadata", {}),
            )
            tree._nodes[nid] = node
            if node.parent_id:
                tree._children.setdefault(node.parent_id, []).append(nid)

        tree._active_leaf_id = data.get("active_leaf_id")
        tree._root_id = data.get("root_id")
        return tree
