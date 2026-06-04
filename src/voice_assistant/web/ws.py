"""WebSocket 连接管理与端点"""
import asyncio
import base64
import logging
from concurrent.futures import Future, ThreadPoolExecutor

from fastapi import WebSocket, WebSocketDisconnect

from voice_assistant.agent.events import EventType
from voice_assistant.audio.cloud_asr import RealtimeASRSession
from voice_assistant.config import config
from voice_assistant.core import VoiceSession
from voice_assistant.db import create_conversation, get_conversation_history, save_message
from voice_assistant.security.ws_auth import is_auth_required, verify_token
from voice_assistant.web.middleware import rate_limiter

logger = logging.getLogger(__name__)

# 客户端会话存储
sessions: dict[str, VoiceSession] = {}

# 待确认操作（用 concurrent.futures.Future 才能在同步线程里 .result(timeout=...)）
pending_confirms: dict[str, Future] = {}

# 每个客户端的流式 ASR 会话
streaming_asr: dict[str, RealtimeASRSession] = {}


def get_or_create_session(client_id: str) -> VoiceSession:
    """获取或创建客户端会话"""
    if client_id not in sessions:
        session = VoiceSession(
            max_response_length=200,
            on_intent_detected=lambda intent, conf: logger.info(f"[{client_id}] Intent: {intent} ({conf})"),
        )
        session.initialize()
        sessions[client_id] = session
        logger.info(f"[WebUI] 创建新会话: {client_id}")
    return sessions[client_id]


def cleanup_session(client_id: str):
    """清理客户端会话"""
    if client_id in sessions:
        sessions[client_id].cleanup()
        del sessions[client_id]
        logger.info(f"[WebUI] 清理会话: {client_id}")
    asr = streaming_asr.pop(client_id, None)
    if asr:
        try:
            asr.stop()
        except Exception:
            pass


class ConnectionManager:
    """WebSocket 连接管理"""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"[WebUI] 客户端连接: {client_id}")

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(f"[WebUI] 客户端断开: {client_id}")

    async def send_message(self, client_id: str, message: dict):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_json(message)


manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket 端点 - 处理实时通信"""
    # WebSocket 认证检查
    client_host = websocket.client.host if websocket.client else None
    if is_auth_required(client_host):
        token = websocket.query_params.get("token", "")
        if not verify_token(token, client_id):
            await websocket.close(code=4001, reason="认证失败：无效或过期的令牌")
            logger.warning(f"[WebUI] WebSocket 认证失败: client_id={client_id}, host={client_host}")
            return

    # 速率限制检查
    if not rate_limiter.check(client_id):
        await websocket.send_json({
            "type": "error",
            "message": "请求过于频繁，请稍后再试"
        })
        await websocket.close()
        return

    await manager.connect(websocket, client_id)
    conversation_id = None

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "start_conversation":
                title = data.get("title", "新对话")
                conversation_id = create_conversation(title)
                await manager.send_message(client_id, {
                    "type": "conversation_started",
                    "conversation_id": conversation_id
                })

            elif msg_type == "load_conversation":
                conversation_id = data.get("conversation_id")
                await manager.send_message(client_id, {
                    "type": "conversation_loaded",
                    "conversation_id": conversation_id
                })

            elif msg_type == "start_audio_stream":
                if not conversation_id:
                    conversation_id = create_conversation()

                loop = asyncio.get_event_loop()

                def _on_sentence_end(text: str, _cid: str = client_id, _loop: asyncio.AbstractEventLoop = loop) -> None:
                    asyncio.run_coroutine_threadsafe(
                        manager.send_message(_cid, {"type": "vad_end", "text": text}),
                        _loop,
                    )

                def _on_error(msg: str, _cid: str = client_id, _loop: asyncio.AbstractEventLoop = loop) -> None:
                    asyncio.run_coroutine_threadsafe(
                        manager.send_message(_cid, {"type": "error", "message": f"实时识别错误: {msg}"}),
                        _loop,
                    )

                asr_session = RealtimeASRSession(on_sentence_end=_on_sentence_end, on_error=_on_error)
                try:
                    with ThreadPoolExecutor() as pool:
                        await loop.run_in_executor(pool, asr_session.start)
                    streaming_asr[client_id] = asr_session
                    logger.info(f"[WebUI] 流式 ASR 会话已启动: {client_id}")
                except Exception as e:
                    logger.error(f"[WebUI] 流式 ASR 启动失败: {e}")
                    await manager.send_message(client_id, {"type": "error", "message": "实时识别启动失败，请重试"})

            elif msg_type == "audio_chunk":
                session = streaming_asr.get(client_id)
                if session:
                    try:
                        chunk_bytes = base64.b64decode(data.get("data", ""))
                        session.send_chunk(chunk_bytes)
                    except Exception as e:
                        logger.warning(f"[WebUI] 转发音频块失败: {e}")

            elif msg_type == "stop_audio_stream":
                session = streaming_asr.pop(client_id, None)
                if session:
                    try:
                        with ThreadPoolExecutor() as pool:
                            await asyncio.get_event_loop().run_in_executor(pool, session.stop)
                    except Exception as e:
                        logger.warning(f"[WebUI] 停止流式 ASR 失败: {e}")

            elif msg_type == "audio_data":
                from voice_assistant.web.audio import convert_audio_to_wav

                if not conversation_id:
                    conversation_id = create_conversation()

                audio_base64 = data.get("base64Audio", "")
                audio_format = data.get("format", "audio/wav")

                try:
                    audio_bytes = base64.b64decode(audio_base64)
                    logger.info(f"[WebUI] 收到音频数据: {len(audio_bytes)} bytes, 格式: {audio_format}")
                except Exception as e:
                    logger.error(f"[WebUI] Base64 decode failed: {e}, base64 length: {len(audio_base64)}")
                    await manager.send_message(client_id, {
                        "type": "error",
                        "message": "音频数据解码失败，请重试"
                    })
                    continue

                if len(audio_bytes) < 100:
                    logger.warning(f"[WebUI] 音频数据过小: {len(audio_bytes)} bytes，可能未录制到有效音频")
                    await manager.send_message(client_id, {
                        "type": "error",
                        "message": "录制的音频太短，请重试"
                    })
                    continue

                # 尽早通知前端：音频已收到，正在识别
                await manager.send_message(client_id, {"type": "asr_processing"})

                wav_bytes = convert_audio_to_wav(audio_bytes, audio_format)

                try:
                    session = get_or_create_session(client_id)
                    loop = asyncio.get_event_loop()
                    with ThreadPoolExecutor() as pool:
                        text = await loop.run_in_executor(pool, session.recognize, wav_bytes)

                    if text:
                        await manager.send_message(client_id, {
                            "type": "asr_result",
                            "content": text
                        })
                    else:
                        await manager.send_message(client_id, {
                            "type": "error",
                            "message": "未能识别语音，请重试"
                        })

                except Exception as e:
                    logger.error(f"[WebUI] ASR 错误: {e}")
                    await manager.send_message(client_id, {
                        "type": "error",
                        "message": f"语音识别失败: {str(e)}"
                    })

            elif msg_type == "text_message":
                if not conversation_id:
                    conversation_id = create_conversation()

                text = data.get("content", "").strip()
                if text:
                    save_message(conversation_id, "user", text)
                    await process_llm_response(client_id, conversation_id, text)

            elif msg_type == "ping":
                await manager.send_message(client_id, {"type": "pong"})

            elif msg_type == "confirm_response":
                confirm_id = data.get("confirm_id", client_id)
                approved = data.get("approved", False)
                if confirm_id in pending_confirms:
                    future = pending_confirms.pop(confirm_id)
                    future.set_result(approved)
                else:
                    logger.warning(f"[WebUI] 收到未知确认响应: {confirm_id}")

            elif msg_type == "replay_tts":
                text = data.get("content", "")
                if text:
                    await manager.send_message(client_id, {"type": "tts_generating"})
                    try:
                        session = get_or_create_session(client_id)
                        loop = asyncio.get_event_loop()
                        with ThreadPoolExecutor() as pool:
                            audio_data = await loop.run_in_executor(pool, session.synthesize, text)

                        if audio_data:
                            audio_b64 = base64.b64encode(audio_data).decode("utf-8")
                            await manager.send_message(client_id, {
                                "type": "tts_audio",
                                "data": audio_b64,
                                "format": "mp3"
                            })
                        else:
                            await manager.send_message(client_id, {
                                "type": "error",
                                "message": "语音合成失败"
                            })
                    except Exception as e:
                        logger.error(f"[WebUI] TTS 重播错误: {e}")
                        await manager.send_message(client_id, {
                            "type": "error",
                            "message": f"语音合成失败: {str(e)}"
                        })

    except WebSocketDisconnect:
        manager.disconnect(client_id)
        cleanup_session(client_id)
    except Exception as e:
        logger.error(f"[WebUI] WebSocket 错误: {e}")
        manager.disconnect(client_id)
        cleanup_session(client_id)


async def process_llm_response(client_id: str, conversation_id: str, user_text: str):
    """处理 LLM 响应（流式优先，回退到同步）"""
    await manager.send_message(client_id, {"type": "llm_thinking"})

    try:
        session = get_or_create_session(client_id)
        history = get_conversation_history(conversation_id, limit=10)
        session.set_history(history)

        loop = asyncio.get_event_loop()

        def confirm_callback(tool_name: str, arguments: dict, guard_result) -> bool:
            """同步回调 — 通过 concurrent.futures.Future 等待前端确认"""
            future: Future | None = None
            confirm_id = None
            try:
                future = Future()
                confirm_id = f"{client_id}_{tool_name}_{id(future)}"
                pending_confirms[confirm_id] = future

                asyncio.run_coroutine_threadsafe(
                    manager.send_message(client_id, {
                        "type": "confirm_required",
                        "confirm_id": confirm_id,
                        "tool_name": tool_name,
                        "arguments": arguments,
                        "message": guard_result.message,
                        "level": guard_result.action.value,
                    }),
                    loop
                )

                timeout = config.agent.confirmation_timeout
                return future.result(timeout=timeout)
            except Exception as e:
                logger.error(f"[WebUI] 确认回调错误: {e}")
                return False
            finally:
                if confirm_id is not None:
                    pending_confirms.pop(confirm_id, None)

        def on_execution_start():
            asyncio.run_coroutine_threadsafe(
                manager.send_message(client_id, {
                    "type": "executing",
                    "message": "正在执行操作..."
                }),
                loop
            )

        def on_execution_end():
            asyncio.run_coroutine_threadsafe(
                manager.send_message(client_id, {
                    "type": "execution_complete",
                    "message": "操作执行完成"
                }),
                loop
            )

        session._on_execution_start = on_execution_start
        session._on_execution_end = on_execution_end
        session._confirm_callback = confirm_callback

        # 尝试流式处理
        full_response = ""
        use_stream = session._orchestrator is not None

        if use_stream:
            import queue


            event_queue: queue.Queue = queue.Queue()
            stream_error = [None]

            def _run_stream():
                try:
                    for event in session.process_text_stream(user_text, history):
                        event_queue.put(event)
                except Exception as e:
                    stream_error[0] = e
                finally:
                    event_queue.put(None)

            with ThreadPoolExecutor() as pool:
                pool.submit(_run_stream)

                while True:
                    try:
                        event = event_queue.get(timeout=0.05)
                    except queue.Empty:
                        await asyncio.sleep(0.01)
                        continue

                    if event is None:
                        break

                    event_type = event.type if isinstance(event.type, str) else event.type.value

                    if event_type == EventType.MESSAGE_DELTA.value:
                        full_response += (event.content or "")
                        await manager.send_message(client_id, {
                            "type": "llm_stream",
                            "content": event.content,
                        })

                    elif event_type == EventType.TOOL_CALL.value:
                        await manager.send_message(client_id, {
                            "type": "tool_call",
                            "tool_name": event.tool_name,
                            "tool_arguments": event.tool_arguments,
                            "tool_call_id": event.tool_call_id,
                        })

                    elif event_type == EventType.TOOL_EXECUTION_START.value:
                        await manager.send_message(client_id, {
                            "type": "executing",
                            "tool_name": event.tool_name,
                            "tool_call_id": event.tool_call_id,
                            "message": f"执行: {event.tool_name}",
                        })

                    elif event_type == EventType.TOOL_EXECUTION_END.value:
                        msg = {
                            "type": "execution_complete",
                            "tool_name": event.tool_name,
                            "tool_call_id": event.tool_call_id,
                            "success": event.tool_success,
                            "message": f"{event.tool_name}: {event.tool_result or '完成'}",
                        }
                        if event.tool_result_data:
                            msg["data"] = event.tool_result_data
                        if event.tool_display_hint and event.tool_display_hint != "text":
                            msg["display_hint"] = event.tool_display_hint
                        if event.duration_ms is not None:
                            msg["duration_ms"] = event.duration_ms
                        await manager.send_message(client_id, msg)

                    elif event_type == EventType.AGENT_END.value:
                        process_result = event.result
                        if process_result and hasattr(process_result, 'response'):
                            full_response = process_result.response
                            if process_result.execution_output:
                                full_response = f"{full_response}\n\n执行结果:\n{process_result.execution_output}"

                    elif event_type == EventType.ERROR.value:
                        await manager.send_message(client_id, {
                            "type": "error",
                            "message": event.content or "处理失败",
                        })
                        return

                if stream_error[0]:
                    raise stream_error[0]

        else:
            # 同步回退路径
            with ThreadPoolExecutor() as pool:
                result = await asyncio.wait_for(
                    loop.run_in_executor(pool, session.process_text, user_text),
                    timeout=60.0
                )
            full_response = result.response
            if result.execution_output:
                full_response = f"{full_response}\n\n执行结果:\n{result.execution_output}"

        # 发送完成标记
        await manager.send_message(client_id, {
            "type": "llm_complete",
            "content": full_response
        })

        # 保存 AI 响应
        save_message(conversation_id, "assistant", full_response)

        # 生成 TTS 音频（非阻塞：超时或失败不影响主流程）
        try:
            await asyncio.wait_for(
                generate_and_send_tts(client_id, conversation_id, full_response),
                timeout=30.0,
            )
        except asyncio.TimeoutError:
            logger.warning("[WebUI] TTS 生成超时（30s），跳过语音播放")
        except Exception as e:
            logger.error(f"[WebUI] TTS 生成失败: {e}")

    except asyncio.TimeoutError:
        logger.error("[WebUI] 处理超时（60秒）")
        await manager.send_message(client_id, {
            "type": "error",
            "message": "处理超时，请重试或尝试更简单的操作"
        })
    except Exception as e:
        logger.error(f"[WebUI] 处理错误: {e}")
        await manager.send_message(client_id, {
            "type": "error",
            "message": f"处理请求失败: {str(e)}"
        })


async def generate_and_send_tts(client_id: str, conversation_id: str, text: str):
    """生成并发送 TTS 音频（使用 VoiceSession）"""
    try:
        await manager.send_message(client_id, {"type": "tts_generating"})

        session = get_or_create_session(client_id)
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as pool:
            audio_data = await asyncio.wait_for(
                loop.run_in_executor(pool, session.synthesize, text),
                timeout=25.0,
            )

        if audio_data:
            audio_b64 = base64.b64encode(audio_data).decode("utf-8")
            await manager.send_message(client_id, {
                "type": "tts_audio",
                "data": audio_b64,
                "format": "mp3"
            })
        else:
            logger.warning("[WebUI] TTS 生成失败（返回空数据）")

    except asyncio.TimeoutError:
        logger.warning("[WebUI] TTS 合成超时（25s），跳过")
    except Exception as e:
        logger.error(f"[WebUI] TTS 错误: {e}")


async def generate_and_send_tts_stream(client_id: str, conversation_id: str, text: str):
    """流式生成并发送 TTS 音频（逐句推送）"""
    try:
        await manager.send_message(client_id, {"type": "tts_generating"})

        session = get_or_create_session(client_id)
        loop = asyncio.get_event_loop()

        chunk_index = 0
        with ThreadPoolExecutor() as pool:
            def stream_tts():
                return list(session.synthesize_stream(text))

            chunks = await asyncio.wait_for(
                loop.run_in_executor(pool, stream_tts),
                timeout=25.0,
            )

        for chunk in chunks:
            if chunk:
                audio_b64 = base64.b64encode(chunk).decode("utf-8")
                await manager.send_message(client_id, {
                    "type": "tts_chunk",
                    "data": audio_b64,
                    "format": "mp3",
                    "chunk_index": chunk_index
                })
                chunk_index += 1
                await asyncio.sleep(0.05)

        await manager.send_message(client_id, {"type": "tts_complete"})

    except Exception as e:
        logger.error(f"[WebUI] 流式TTS错误: {e}")
        await generate_and_send_tts(client_id, conversation_id, text)
