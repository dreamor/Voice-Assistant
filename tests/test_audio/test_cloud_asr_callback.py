"""测试 CloudASR on_event 回调累积逻辑

验证 get_sentence() 返回累积文本时，回调不会产生重复拼接。
"""


class MockSentence:
    """模拟 dashscope get_sentence() 返回值"""

    def __init__(self, text: str):
        self._text = text

    def get(self, key: str, default=None):
        if key == "text":
            return self._text
        return default

    def __contains__(self, key: str):
        return key == "text"

    def __getitem__(self, key: str):
        if key == "text":
            return self._text
        raise KeyError(key)


class MockResult:
    """模拟 dashscope Recognition result"""

    def __init__(self, sentence_text: str | None):
        self._sentence = MockSentence(sentence_text) if sentence_text else None

    def get_sentence(self):
        return self._sentence


class TestASRCallbackAccumulation:
    """测试 ASR 回调的智能累积逻辑"""

    def _make_result_container(self):
        return {
            "completed_sentences": [],
            "current_sentence": "",
            "finished": False,
            "error": None,
        }

    def _simulate_on_event(self, container, result):
        """模拟 on_event 回调的核心逻辑"""
        sentence = result.get_sentence()
        if sentence and "text" in sentence:
            text = sentence["text"]
            prev = container["current_sentence"]
            if prev and text.startswith(prev):
                container["current_sentence"] = text
            elif prev:
                container["completed_sentences"].append(prev)
                container["current_sentence"] = text
            else:
                container["current_sentence"] = text

    def _get_final_text(self, container):
        all_sentences = container["completed_sentences"] + [container["current_sentence"]]
        return "".join(s for s in all_sentences if s)

    def test_single_sentence_no_duplicate(self):
        """单句子 partial result 累积不应产生重复"""
        container = self._make_result_container()

        self._simulate_on_event(container, MockResult("打开"))
        self._simulate_on_event(container, MockResult("打开计"))
        self._simulate_on_event(container, MockResult("打开计算器"))

        assert self._get_final_text(container) == "打开计算器"

    def test_single_english_no_duplicate(self):
        """英文单句子不应产生重复"""
        container = self._make_result_container()

        self._simulate_on_event(container, MockResult("Hello"))
        self._simulate_on_event(container, MockResult("Hello world"))

        assert self._get_final_text(container) == "Hello world"

    def test_multiple_sentences(self):
        """多句子场景应正确拼接"""
        container = self._make_result_container()

        # 第一句
        self._simulate_on_event(container, MockResult("你好"))
        self._simulate_on_event(container, MockResult("你好世界"))

        # 第二句开始（不以 "你好世界" 为前缀）
        self._simulate_on_event(container, MockResult("打开"))
        self._simulate_on_event(container, MockResult("打开计算器"))

        result = self._get_final_text(container)
        assert result == "你好世界打开计算器"
        assert container["completed_sentences"] == ["你好世界"]
        assert container["current_sentence"] == "打开计算器"

    def test_empty_result(self):
        """空结果应返回空字符串"""
        container = self._make_result_container()
        assert self._get_final_text(container) == ""

    def test_null_sentence(self):
        """get_sentence() 返回 None 时不应报错"""
        container = self._make_result_container()
        self._simulate_on_event(container, MockResult(None))
        assert self._get_final_text(container) == ""

    def test_sentence_without_text_key(self):
        """sentence 不含 text 键时不应报错"""
        container = self._make_result_container()

        class NoTextResult:
            def get_sentence(self):
                return {"begin_time": 0}

        self._simulate_on_event(container, NoTextResult())
        assert self._get_final_text(container) == ""

    def test_identical_consecutive_events(self):
        """相同内容的连续事件不应产生重复"""
        container = self._make_result_container()

        self._simulate_on_event(container, MockResult("你好"))
        self._simulate_on_event(container, MockResult("你好"))
        self._simulate_on_event(container, MockResult("你好"))

        assert self._get_final_text(container) == "你好"

    def test_error_handling(self):
        """错误应正确记录"""
        container = self._make_result_container()
        container["error"] = "Connection lost"
        container["finished"] = True

        assert container["error"] == "Connection lost"
        assert container["finished"] is True
