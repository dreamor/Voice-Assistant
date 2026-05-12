/**
 * WebSocket 通信模块
 */

import { state, logger, elements, vadConfig } from './state.js';
import * as ui from './ui.js';

/**
 * 连接 WebSocket
 */
export function connectWebSocket() {
    const wsUrl = `ws://${window.location.host}/ws/${state.clientId}`;
    state.ws = new WebSocket(wsUrl);

    state.ws.onopen = () => {
        logger.info('[WebUI] WebSocket 连接成功');
    };

    state.ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
    };

    state.ws.onclose = () => {
        logger.info('[WebUI] WebSocket 断开，5秒后重连...');
        setTimeout(connectWebSocket, 5000);
    };

    state.ws.onerror = (error) => {
        logger.error('[WebUI] WebSocket 错误:', error);
    };
}

/**
 * 处理 WebSocket 消息
 * @param {Object} data - 消息数据
 */
function handleWebSocketMessage(data) {
    logger.info('[WebUI] 收到消息:', data.type);

    switch (data.type) {
        case 'conversation_started':
            state.conversationId = data.conversation_id;
            break;

        case 'conversation_loaded':
            state.conversationId = data.conversation_id;
            ui.loadConversationMessages(data.conversation_id);
            break;

        case 'user_message':
            ui.addUserMessage(data.content);
            break;

        case 'asr_processing':
            ui.showThinking('正在识别语音...');
            break;

        case 'asr_result':
            handleAsrResult(data);
            break;

        case 'llm_thinking':
            ui.showThinking('AI 正在思考...');
            break;

        case 'executing':
            ui.showThinking(data.message || '正在执行操作...');
            break;

        case 'execution_complete':
            ui.hideThinking();
            break;

        case 'llm_stream':
            ui.hideThinking();
            ui.updateStreamingMessage(data.content);
            break;

        case 'llm_complete':
            ui.finalizeStreamingMessage(data.content);
            break;

        case 'tts_generating':
            ui.showThinking('正在生成语音...');
            break;

        case 'tts_audio':
            ui.hideThinking();
            ui.playAudio(data.data);
            break;

        case 'tts_chunk':
            ui.hideThinking();
            ui.playAudioChunk(data.data, data.chunk_index);
            break;

        case 'tts_complete':
            ui.finalizeAudioPlayback();
            break;

        case 'error':
            ui.hideThinking();
            ui.showError(data.message);
            break;

        case 'pong':
            // 心跳响应
            break;

        case 'confirm_required':
            ui.showConfirmDialog(data);
            break;
    }
}

/**
 * 处理语音识别结果
 * @param {Object} data - ASR 数据
 */
function handleAsrResult(data) {
    ui.hideThinking();
    const recognizedText = data.content?.trim();

    if (recognizedText) {
        ui.addUserMessage(recognizedText);

        if (!state.conversationId) {
            state.ws.send(JSON.stringify({
                type: 'start_conversation',
                title: recognizedText.slice(0, 20)
            }));
            setTimeout(() => {
                sendTextMessage(recognizedText);
            }, 100);
        } else {
            sendTextMessage(recognizedText);
        }

        elements.textInput.value = '';
    } else {
        ui.showError('未能识别语音，请重试');
    }
}

/**
 * 发送文本消息
 * @param {string} text - 消息内容
 */
export function sendTextMessage(text) {
    if (state.ws && state.ws.readyState === WebSocket.OPEN) {
        state.ws.send(JSON.stringify({
            type: 'text_message',
            content: text
        }));
    }
}

/**
 * 发送音频数据
 * @param {string} base64Audio - Base64 编码的音频
 * @param {string} format - 音频格式
 */
export function sendAudioData(base64Audio, format) {
    if (state.ws && state.ws.readyState === WebSocket.OPEN) {
        if (!state.conversationId) {
            state.ws.send(JSON.stringify({
                type: 'start_conversation',
                title: '语音对话'
            }));
        }
        state.ws.send(JSON.stringify({
            type: 'audio_data',
            base64Audio: base64Audio,
            format: format || 'audio/webm'
        }));
    }
}

/**
 * 重播 TTS
 * @param {string} text - 要播放的文本
 */
export function replayTTS(text) {
    if (state.ws && state.ws.readyState === WebSocket.OPEN) {
        state.ws.send(JSON.stringify({
            type: 'replay_tts',
            content: text
        }));
    }
}

/**
 * 处理确认响应
 * @param {string} confirmId - 确认 ID
 * @param {boolean} approved - 是否批准
 */
export function handleConfirmResponse(confirmId, approved) {
    if (state.ws && state.ws.readyState === WebSocket.OPEN) {
        state.ws.send(JSON.stringify({
            type: 'confirm_response',
            confirm_id: confirmId,
            approved: approved
        }));
    }
}

/**
 * 开始新对话
 * @param {string} title - 对话标题
 */
export function startConversation(title) {
    if (state.ws && state.ws.readyState === WebSocket.OPEN) {
        state.ws.send(JSON.stringify({
            type: 'start_conversation',
            title: title
        }));
    }
}
