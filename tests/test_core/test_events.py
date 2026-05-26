"""EventBus 事件系统测试"""
from voice_assistant.core.events import Event, EventBus, EventName, get_event_bus


class TestEventName:
    def test_all_event_names(self):
        assert EventName.AGENT_START == "agent_start"
        assert EventName.AGENT_END == "agent_end"
        assert EventName.TOOL_BEFORE == "tool_before"
        assert EventName.TOOL_AFTER == "tool_after"
        assert EventName.MESSAGE_CREATED == "message_created"
        assert EventName.COMPACT_START == "compact_start"
        assert EventName.COMPACT_END == "compact_end"
        assert EventName.ERROR == "error"

    def test_is_str_enum(self):
        assert isinstance(EventName.AGENT_START, str)
        assert EventName.AGENT_START == "agent_start"


class TestEvent:
    def test_default_values(self):
        e = Event(name=EventName.TOOL_BEFORE, data={"tool": "read"})
        assert e.name == EventName.TOOL_BEFORE
        assert e.data == {"tool": "read"}
        assert e.cancelled is False

    def test_custom_values(self):
        e = Event(name="custom_event", data={"x": 1}, cancelled=True)
        assert e.name == "custom_event"
        assert e.cancelled is True

    def test_string_event_name(self):
        e = Event(name="my_custom_event")
        assert e.name == "my_custom_event"
        assert e.data == {}


class TestEventBus:
    def test_on_and_emit(self):
        bus = EventBus()
        received = []
        bus.on(EventName.TOOL_AFTER, lambda e: received.append(e.data))

        bus.emit(Event(name=EventName.TOOL_AFTER, data={"tool": "read", "success": True}))

        assert len(received) == 1
        assert received[0]["tool"] == "read"

    def test_multiple_handlers(self):
        bus = EventBus()
        results = []
        bus.on(EventName.AGENT_START, lambda e: results.append("a"))
        bus.on(EventName.AGENT_START, lambda e: results.append("b"))

        bus.emit(Event(name=EventName.AGENT_START))

        assert results == ["a", "b"]

    def test_off_removes_handler(self):
        bus = EventBus()
        results = []
        def handler(e):
            results.append("called")
        bus.on(EventName.ERROR, handler)
        bus.emit(Event(name=EventName.ERROR))
        assert results == ["called"]

        bus.off(EventName.ERROR, handler)
        bus.emit(Event(name=EventName.ERROR))
        assert results == ["called"]  # 不再调用

    def test_off_nonexistent_handler_noop(self):
        bus = EventBus()
        bus.off(EventName.ERROR, lambda e: None)  # 不应抛出异常

    def test_emit_no_handlers_noop(self):
        bus = EventBus()
        bus.emit(Event(name=EventName.COMPACT_START))  # 不应抛出异常

    def test_handler_exception_logged_not_raised(self):
        bus = EventBus()
        bus.on(EventName.ERROR, lambda e: 1 / 0)
        # 不应抛出异常，错误被日志记录
        bus.emit(Event(name=EventName.ERROR))

    def test_string_event_name(self):
        bus = EventBus()
        received = []
        bus.on("custom_event", lambda e: received.append(e.data))

        bus.emit(Event(name="custom_event", data={"key": "val"}))

        assert len(received) == 1
        assert received[0]["key"] == "val"

    def test_mixed_enum_and_string_event_name(self):
        bus = EventBus()
        received = []
        bus.on(EventName.TOOL_BEFORE, lambda e: received.append("enum"))
        bus.on("tool_before", lambda e: received.append("string"))

        # EventName.TOOL_BEFORE.value == "tool_before"
        bus.emit(Event(name=EventName.TOOL_BEFORE))
        # 两个 handler 都应被触发，因为 key 都是 "tool_before"
        assert "enum" in received
        assert "string" in received

    def test_clear(self):
        bus = EventBus()
        results = []
        bus.on(EventName.AGENT_END, lambda e: results.append(1))
        bus.on(EventName.ERROR, lambda e: results.append(2))

        bus.clear()
        bus.emit(Event(name=EventName.AGENT_END))
        bus.emit(Event(name=EventName.ERROR))

        assert results == []

    def test_event_data_isolation(self):
        bus = EventBus()
        received = []
        bus.on(EventName.COMPACT_END, lambda e: received.append(e.data.copy()))

        bus.emit(Event(name=EventName.COMPACT_END, data={"removed": 5}))
        bus.emit(Event(name=EventName.COMPACT_END, data={"removed": 10}))

        assert received[0]["removed"] == 5
        assert received[1]["removed"] == 10

    def test_cancelled_event_still_dispatched(self):
        """EventBus 不可拦截 — cancelled 标记由订阅者检查，不影响分发"""
        bus = EventBus()
        received = []
        bus.on(EventName.TOOL_BEFORE, lambda e: received.append("seen"))

        event = Event(name=EventName.TOOL_BEFORE, cancelled=True)
        bus.emit(event)

        # EventBus 不检查 cancelled，所有 handler 都执行
        assert received == ["seen"]


class TestGetEventBus:
    def test_singleton(self):
        bus1 = get_event_bus()
        bus2 = get_event_bus()
        assert bus1 is bus2

    def test_is_event_bus(self):
        bus = get_event_bus()
        assert isinstance(bus, EventBus)

    def test_clear_between_tests(self):
        """测试之间清理全局总线"""
        bus = get_event_bus()
        bus.clear()
        results = []
        bus.on(EventName.AGENT_START, lambda e: results.append(1))
        bus.emit(Event(name=EventName.AGENT_START))
        assert results == [1]
        bus.clear()
