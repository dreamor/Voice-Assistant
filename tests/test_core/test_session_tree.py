"""SessionTree 树形会话结构测试"""
from voice_assistant.core.session_tree import SessionTree, TreeNode


class TestTreeNode:
    def test_to_dict(self):
        node = TreeNode(id="a", parent_id=None, role="user", content="hi", timestamp=1.0)
        d = node.to_dict()
        assert d["id"] == "a"
        assert d["parent_id"] is None
        assert d["role"] == "user"
        assert d["content"] == "hi"
        assert d["metadata"] == {}

    def test_to_message(self):
        node = TreeNode(id="a", parent_id=None, role="assistant", content="hello", timestamp=1.0)
        msg = node.to_message()
        assert msg == {"role": "assistant", "content": "hello"}

    def test_metadata(self):
        node = TreeNode(id="a", parent_id=None, role="tool", content="ok", timestamp=1.0,
                        metadata={"tool_name": "read"})
        assert node.metadata["tool_name"] == "read"


class TestSessionTreeBasic:
    def test_empty_tree(self):
        tree = SessionTree()
        assert tree.node_count() == 0
        assert tree.active_leaf_id is None
        assert tree.root_id is None
        assert tree.to_messages() == []

    def test_append_single(self):
        tree = SessionTree()
        nid = tree.append("user", "hello")
        assert tree.node_count() == 1
        assert tree.active_leaf_id == nid
        assert tree.root_id == nid

    def test_append_chain(self):
        tree = SessionTree()
        n1 = tree.append("user", "hi")
        tree.append("assistant", "hello")
        n3 = tree.append("user", "how are you?")

        assert tree.node_count() == 3
        assert tree.active_leaf_id == n3
        assert tree.root_id == n1

        branch = tree.get_active_branch()
        assert len(branch) == 3
        assert branch[0].content == "hi"
        assert branch[2].content == "how are you?"

    def test_to_messages(self):
        tree = SessionTree()
        tree.append("user", "hi")
        tree.append("assistant", "hello")

        msgs = tree.to_messages()
        assert msgs == [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]

    def test_get_node(self):
        tree = SessionTree()
        nid = tree.append("user", "test")
        node = tree.get_node(nid)
        assert node is not None
        assert node.content == "test"

    def test_get_node_nonexistent(self):
        tree = SessionTree()
        assert tree.get_node("nonexistent") is None


class TestSessionTreeBranch:
    def test_branch_creates_new_path(self):
        tree = SessionTree()
        n1 = tree.append("user", "hi")
        tree.append("assistant", "hello")

        # 从 n1 创建分支
        n3 = tree.branch(n1, role="assistant", content="hey there")

        assert tree.node_count() == 3
        assert tree.active_leaf_id == n3

        # 新分支路径
        branch = tree.get_active_branch()
        assert len(branch) == 2
        assert branch[0].content == "hi"
        assert branch[1].content == "hey there"

    def test_switch_branch(self):
        tree = SessionTree()
        n1 = tree.append("user", "hi")
        n2 = tree.append("assistant", "hello")
        n3 = tree.branch(n1, role="assistant", content="hey")

        # 当前在 n3 分支
        assert tree.active_leaf_id == n3

        # 切换回 n2 分支
        tree.switch_branch(n2)
        branch = tree.get_active_branch()
        assert branch[-1].content == "hello"

    def test_list_branches(self):
        tree = SessionTree()
        n1 = tree.append("user", "hi")
        tree.append("assistant", "hello")
        tree.branch(n1, role="assistant", content="hey")

        branches = tree.list_branches(n1)
        assert len(branches) == 2

        contents = {b[-1].content for b in branches}
        assert "hello" in contents
        assert "hey" in contents

    def test_branch_nonexistent_raises(self):
        tree = SessionTree()
        try:
            tree.branch("nonexistent")
            assert False, "应该抛出 ValueError"
        except ValueError:
            pass

    def test_switch_nonexistent_raises(self):
        tree = SessionTree()
        try:
            tree.switch_branch("nonexistent")
            assert False, "应该抛出 ValueError"
        except ValueError:
            pass


class TestSessionTreeSerialization:
    def test_to_dict_and_from_dict(self):
        tree = SessionTree()
        n1 = tree.append("user", "hi")
        tree.append("assistant", "hello")
        n3 = tree.branch(n1, role="assistant", content="hey")

        data = tree.to_dict()
        restored = SessionTree.from_dict(data)

        assert restored.node_count() == 3
        assert restored.active_leaf_id == n3
        assert restored.root_id == n1

        # 验证分支结构
        branches = restored.list_branches(n1)
        assert len(branches) == 2

    def test_roundtrip_preserves_messages(self):
        tree = SessionTree()
        tree.append("user", "hello")
        tree.append("assistant", "world")

        data = tree.to_dict()
        restored = SessionTree.from_dict(data)

        assert restored.to_messages() == [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "world"},
        ]


class TestSessionTreeFromMessages:
    def test_from_flat_messages(self):
        tree = SessionTree()
        tree.from_messages([
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
            {"role": "user", "content": "how are you?"},
        ])

        assert tree.node_count() == 3
        assert tree.to_messages() == [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
            {"role": "user", "content": "how are you?"},
        ]

    def test_from_empty_messages(self):
        tree = SessionTree()
        tree.from_messages([])
        assert tree.node_count() == 0

    def test_from_messages_with_none_content(self):
        tree = SessionTree()
        tree.from_messages([
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": None},
        ])
        assert tree.node_count() == 2
        msgs = tree.to_messages()
        assert msgs[1]["content"] == ""

    def test_from_messages_replaces_existing(self):
        tree = SessionTree()
        tree.append("user", "old")
        tree.from_messages([{"role": "user", "content": "new"}])
        assert tree.node_count() == 1
        assert tree.to_messages() == [{"role": "user", "content": "new"}]


class TestSessionTreeMetadata:
    def test_append_with_metadata(self):
        tree = SessionTree()
        nid = tree.append("tool", "result", tool_name="read_file", file_path="/tmp/x")
        node = tree.get_node(nid)
        assert node.metadata["tool_name"] == "read_file"
        assert node.metadata["file_path"] == "/tmp/x"

    def test_branch_with_metadata(self):
        tree = SessionTree()
        n1 = tree.append("user", "hi")
        n2 = tree.branch(n1, role="assistant", content="hello", model="gpt-4o")
        node = tree.get_node(n2)
        assert node.metadata["model"] == "gpt-4o"
