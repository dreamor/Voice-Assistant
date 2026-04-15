/**
 * Voice Assistant Web UI - 前端逻辑
 */

// 生产环境禁用调试日志
const logger = {
    debug: () => {},
    info: () => {},
    warn: () => {},
    error: (...args) => logger.error('[WebUI]', ...args)
};

// 全局状态
const state = {
    ws: null,
    clientId: generateClientId(),
    conversationId: null,
    isRecording: false,
    mediaRecorder: null,
    audioChunks: [],
    currentMessageDiv: null,
    config: {},
    models: []
};

// DOM 元素
const elements = {
    messagesContainer: document.getElementById('messages-container'),
    messages: document.getElementById('messages'),
    welcomeScreen: document.getElementById('welcome-screen'),
    textInput: document.getElementById('text-input'),
    sendBtn: document.getElementById('send-btn'),
    recordBtn: document.getElementById('record-btn'),
    stopRecordBtn: document.getElementById('stop-record-btn'),
    recordingIndicator: document.getElementById('recording-indicator'),
    historyList: document.getElementById('history-list'),
    newChatBtn: document.getElementById('new-chat-btn'),
    settingsBtn: document.getElementById('settings-btn'),
    settingsModal: document.getElementById('settings-modal'),
    closeSettings: document.getElementById('close-settings'),
    saveSettings: document.getElementById('save-settings'),
    resetSettings: document.getElementById('reset-settings'),
    modelSelect: document.getElementById('model-select'),
    settingModel: document.getElementById('setting-model'),
    settingTemperature: document.getElementById('setting-temperature'),
    tempValue: document.getElementById('temp-value'),
    settingMaxTokens: document.getElementById('setting-max-tokens'),
    settingTtsVoice: document.getElementById('setting-tts-voice'),
    settingUseLocalAsr: document.getElementById('setting-use-local-asr'),
    audioPlayer: document.getElementById('audio-player'),
    quickActions: document.querySelectorAll('.quick-action')
};

// 初始化
async function init() {
    logger.info('[WebUI] 初始化...');

    // 加载配置
    await loadConfig();

    // 加载模型列表
    await loadModels();

    // 加载历史记录
    await loadHistory();

    // 连接 WebSocket
    connectWebSocket();

    // 绑定事件
    bindEvents();

    // 自动调整输入框高度
    autoResizeTextarea();
}

// 生成客户端 ID
function generateClientId() {
    return 'client_' + Math.random().toString(36).substr(2, 9);
}

// 连接 WebSocket
function connectWebSocket() {
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

// 处理 WebSocket 消息
function handleWebSocketMessage(data) {
    logger.info('[WebUI] 收到消息:', data.type);

    switch (data.type) {
        case 'conversation_started':
            state.conversationId = data.conversation_id;
            break;

        case 'conversation_loaded':
            state.conversationId = data.conversation_id;
            loadConversationMessages(data.conversation_id);
            break;

        case 'user_message':
            addUserMessage(data.content);
            break;

        case 'asr_processing':
            showThinking('正在识别语音...');
            break;

        case 'asr_result':
            // 语音识别完成，将结果填入输入框，让用户确认
            hideThinking();
            elements.textInput.value = data.content;
            elements.textInput.focus();
            // 可选：自动发送（如果不需要用户确认，可以取消注释下面这行）
            // setTimeout(() => sendMessage(), 500);
            break;

        case 'llm_thinking':
            showThinking('AI 正在思考...');
            break;

        case 'executing':
            showThinking(data.message || '正在执行操作...');
            break;

        case 'execution_complete':
            hideThinking();
            break;

        case 'llm_stream':
            hideThinking();
            updateStreamingMessage(data.content);
            break;

        case 'llm_complete':
            finalizeStreamingMessage(data.content);
            break;

        case 'tts_generating':
            showThinking('正在生成语音...');
            break;

        case 'tts_audio':
            hideThinking();
            playAudio(data.data);
            break;

        case 'error':
            hideThinking();
            showError(data.message);
            break;

        case 'pong':
            // 心跳响应
            break;
    }
}

// 加载配置
async function loadConfig() {
    try {
        const response = await fetch('/api/config');
        state.config = await response.json();

        // 更新设置面板
        elements.settingModel.value = state.config.llm.model || '';
        elements.settingTemperature.value = state.config.llm.temperature || 0.7;
        elements.tempValue.textContent = state.config.llm.temperature || 0.7;
        elements.settingMaxTokens.value = state.config.llm.max_tokens || 2000;
        elements.settingTtsVoice.value = state.config.audio.edge_tts_voice || 'zh-CN-XiaoxiaoNeural';
        elements.settingUseLocalAsr.checked = state.config.asr.use_local !== false;
    } catch (error) {
        logger.error('[WebUI] 加载配置失败:', error);
    }
}

// 加载模型列表
async function loadModels() {
    try {
        const response = await fetch('/api/models');
        const data = await response.json();
        state.models = data.models || [];

        // 更新设置面板中的模型 datalist
        updateModelDatalist();
    } catch (error) {
        logger.error('[WebUI] 加载模型列表失败:', error);
    }
}

// 更新模型 datalist
function updateModelDatalist() {
    const datalist = document.getElementById('model-list');
    if (datalist) {
        datalist.innerHTML = state.models.map(model =>
            `<option value="${model}">${model}</option>`
        ).join('');
    }
}

// 加载历史记录
async function loadHistory() {
    try {
        const response = await fetch('/api/history');
        const data = await response.json();

        elements.historyList.innerHTML = data.conversations.map(conv => `
            <div class="history-item ${conv.id === state.conversationId ? 'active' : ''}" data-id="${conv.id}">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                </svg>
                <span>${escapeHtml(conv.title)}</span>
                <button class="btn-icon delete-btn" data-id="${conv.id}" title="删除">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                </button>
            </div>
        `).join('');

        // 绑定历史项点击事件
        document.querySelectorAll('.history-item').forEach(item => {
            item.addEventListener('click', (e) => {
                if (e.target.closest('.delete-btn')) return;
                const id = item.dataset.id;
                loadConversation(id);
            });
        });

        // 绑定删除按钮事件
        document.querySelectorAll('.delete-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const id = btn.dataset.id;
                deleteConversation(id);
            });
        });
    } catch (error) {
        logger.error('[WebUI] 加载历史记录失败:', error);
    }
}

// 加载指定对话
async function loadConversation(id) {
    try {
        const response = await fetch(`/api/history/${id}`);
        const data = await response.json();

        if (data.error) {
            showError(data.error);
            return;
        }

        state.conversationId = id;

        // 隐藏欢迎界面
        elements.welcomeScreen.style.display = 'none';

        // 清空并重新渲染消息
        elements.messages.innerHTML = '';
        data.messages.forEach(msg => {
            if (msg.role === 'user') {
                addUserMessage(msg.content, false);
            } else {
                addAssistantMessage(msg.content, false);
            }
        });

        // 更新历史列表高亮
        document.querySelectorAll('.history-item').forEach(item => {
            item.classList.toggle('active', item.dataset.id === id);
        });

        scrollToBottom();
    } catch (error) {
        logger.error('[WebUI] 加载对话失败:', error);
    }
}

// 加载对话消息（WebSocket 回调用）
async function loadConversationMessages(id) {
    try {
        const response = await fetch(`/api/history/${id}`);
        const data = await response.json();

        if (!data.error) {
            elements.welcomeScreen.style.display = 'none';
            elements.messages.innerHTML = '';
            data.messages.forEach(msg => {
                if (msg.role === 'user') {
                    addUserMessage(msg.content, false);
                } else {
                    addAssistantMessage(msg.content, false);
                }
            });
            scrollToBottom();
        }
    } catch (error) {
        logger.error('[WebUI] 加载消息失败:', error);
    }
}

// 删除对话
async function deleteConversation(id) {
    if (!confirm('确定要删除这个对话吗？')) return;

    try {
        const response = await fetch(`/api/history/${id}`, { method: 'DELETE' });
        const data = await response.json();

        if (data.success) {
            if (state.conversationId === id) {
                state.conversationId = null;
                elements.messages.innerHTML = '';
                elements.welcomeScreen.style.display = 'flex';
            }
            loadHistory();
        }
    } catch (error) {
        logger.error('[WebUI] 删除对话失败:', error);
    }
}

// 添加用户消息
function addUserMessage(content, animate = true) {
    elements.welcomeScreen.style.display = 'none';

    const messageDiv = document.createElement('div');
    messageDiv.className = 'message user';
    if (!animate) messageDiv.style.animation = 'none';

    messageDiv.innerHTML = `
        <div class="message-avatar">我</div>
        <div class="message-content">
            <p>${escapeHtml(content)}</p>
        </div>
    `;

    elements.messages.appendChild(messageDiv);
    scrollToBottom();
}

// 添加 AI 消息（开始流式）
function startStreamingMessage() {
    elements.welcomeScreen.style.display = 'none';

    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant';

    messageDiv.innerHTML = `
        <div class="message-avatar">AI</div>
        <div class="message-content">
            <span class="streaming-text"></span><span class="streaming-cursor"></span>
            <div class="message-actions">
                <button class="message-action-btn copy-btn">复制</button>
                <button class="message-action-btn replay-btn">重播</button>
            </div>
        </div>
    `;

    elements.messages.appendChild(messageDiv);
    scrollToBottom();

    state.currentMessageDiv = messageDiv;

    // 绑定按钮事件
    messageDiv.querySelector('.copy-btn').addEventListener('click', () => {
        const text = messageDiv.querySelector('.streaming-text').textContent;
        navigator.clipboard.writeText(text);
    });

    messageDiv.querySelector('.replay-btn').addEventListener('click', () => {
        const text = messageDiv.querySelector('.streaming-text').textContent;
        replayTTS(text);
    });

    return messageDiv;
}

// 更新流式消息
function updateStreamingMessage(content) {
    if (!state.currentMessageDiv) {
        startStreamingMessage();
    }

    const textSpan = state.currentMessageDiv.querySelector('.streaming-text');
    textSpan.innerHTML = formatMessageContent(content);
    scrollToBottom();
}

// 完成流式消息
function finalizeStreamingMessage(content) {
    if (state.currentMessageDiv) {
        const cursor = state.currentMessageDiv.querySelector('.streaming-cursor');
        if (cursor) cursor.remove();
        state.currentMessageDiv = null;
    }
    scrollToBottom();
}

// 添加 AI 消息（非流式）
function addAssistantMessage(content, animate = true) {
    elements.welcomeScreen.style.display = 'none';

    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant';
    if (!animate) messageDiv.style.animation = 'none';

    messageDiv.innerHTML = `
        <div class="message-avatar">AI</div>
        <div class="message-content">
            ${formatMessageContent(content)}
            <div class="message-actions">
                <button class="message-action-btn copy-btn">复制</button>
                <button class="message-action-btn replay-btn">重播</button>
            </div>
        </div>
    `;

    elements.messages.appendChild(messageDiv);
    scrollToBottom();

    // 绑定按钮事件
    messageDiv.querySelector('.copy-btn').addEventListener('click', () => {
        navigator.clipboard.writeText(content);
    });

    messageDiv.querySelector('.replay-btn').addEventListener('click', () => {
        replayTTS(content);
    });
}

// 格式化消息内容（支持 Markdown 子集）
function formatMessageContent(content) {
    // 转义 HTML
    let html = escapeHtml(content);

    // 代码块
    html = html.replace(/```(\w+)?\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>');

    // 行内代码
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

    // 粗体
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

    // 斜体
    html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');

    // 换行
    html = html.replace(/\n/g, '<br>');

    return html;
}

// 显示思考中
function showThinking(text) {
    hideThinking();

    const thinkingDiv = document.createElement('div');
    thinkingDiv.className = 'message assistant thinking';
    thinkingDiv.id = 'thinking-indicator';

    thinkingDiv.innerHTML = `
        <div class="message-avatar">AI</div>
        <div class="message-content">
            <div class="thinking-indicator">
                <div class="thinking-dots">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
                <span>${escapeHtml(text)}</span>
            </div>
        </div>
    `;

    elements.messages.appendChild(thinkingDiv);
    scrollToBottom();
}

// 隐藏思考中
function hideThinking() {
    const thinkingDiv = document.getElementById('thinking-indicator');
    if (thinkingDiv) {
        thinkingDiv.remove();
    }
}

// 显示错误
function showError(message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'message assistant';
    errorDiv.innerHTML = `
        <div class="message-avatar" style="background: #EF4444; color: white;">!</div>
        <div class="message-content" style="border-color: #EF4444;">
            <p style="color: #EF4444;">${escapeHtml(message)}</p>
        </div>
    `;
    elements.messages.appendChild(errorDiv);
    scrollToBottom();
}

// 播放音频
function playAudio(base64Data) {
    const audioSrc = `data:audio/mp3;base64,${base64Data}`;
    elements.audioPlayer.src = audioSrc;
    elements.audioPlayer.play().catch(error => {
        logger.error('[WebUI] 播放音频失败:', error);
    });
}

// 重播 TTS
function replayTTS(text) {
    if (state.ws && state.ws.readyState === WebSocket.OPEN) {
        state.ws.send(JSON.stringify({
            type: 'replay_tts',
            content: text
        }));
    }
}

// 滚动到底部
function scrollToBottom() {
    elements.messagesContainer.scrollTop = elements.messagesContainer.scrollHeight;
}

// 发送消息
function sendMessage() {
    const text = elements.textInput.value.trim();
    if (!text) return;

    // 清空输入框
    elements.textInput.value = '';
    elements.textInput.style.height = 'auto';

    // 如果没有对话，创建新对话并等待响应
    if (!state.conversationId) {
        state.ws.send(JSON.stringify({
            type: 'start_conversation',
            title: text.slice(0, 20)
        }));
        // 等待 conversation_started 事件后再发送消息
        // 使用 setTimeout 延迟发送，确保 WebSocket 消息顺序
        setTimeout(() => {
            sendTextMessage(text);
        }, 100);
    } else {
        sendTextMessage(text);
    }

    // 显示用户消息
    addUserMessage(text);
}

// 发送文本消息（内部函数）
function sendTextMessage(text) {
    if (state.ws && state.ws.readyState === WebSocket.OPEN) {
        state.ws.send(JSON.stringify({
            type: 'text_message',
            content: text
        }));
    }
}

// 开始录音
async function startRecording() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

        // 检查支持的 MIME 类型，优先使用 wav 格式
        let mimeType = 'audio/wav';
        if (!MediaRecorder.isTypeSupported('audio/wav')) {
            // 尝试其他常见格式
            const types = [
                'audio/webm;codecs=opus',
                'audio/webm',
                'audio/ogg;codecs=opus',
                'audio/ogg'
            ];
            for (const t of types) {
                if (MediaRecorder.isTypeSupported(t)) {
                    mimeType = t;
                    break;
                }
            }
        }

        logger.info('[WebUI] 使用音频格式:', mimeType);

        state.mediaRecorder = new MediaRecorder(stream, { mimeType });
        state.audioChunks = [];
        state.mimeType = mimeType;

        state.mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                state.audioChunks.push(event.data);
            }
        };

        state.mediaRecorder.onstop = async () => {
            const audioBlob = new Blob(state.audioChunks, { type: state.mimeType || 'audio/webm' });
            const base64Audio = await blobToBase64(audioBlob);

            logger.info('[WebUI] 录音完成, 大小:', audioBlob.size, 'bytes, 格式:', state.mimeType);

            // 如果没有对话，创建新对话
            if (!state.conversationId) {
                state.ws.send(JSON.stringify({
                    type: 'start_conversation',
                    title: '语音对话'
                }));
            }

            // 发送音频数据（包含实际格式信息）
            state.ws.send(JSON.stringify({
                type: 'audio_data',
                data: base64Audio,
                format: state.mimeType || 'audio/webm'
            }));

            // 停止所有音轨
            stream.getTracks().forEach(track => track.stop());
        };

        // 每 100ms 收集一次数据，确保录音不会丢失
        state.mediaRecorder.start(100);
        state.isRecording = true;

        // 更新 UI
        elements.recordBtn.classList.add('recording');
        elements.recordingIndicator.classList.add('active');

    } catch (error) {
        logger.error('[WebUI] 录音失败:', error);
        showError('无法访问麦克风，请检查权限设置');
    }
}

// 停止录音
function stopRecording() {
    if (state.mediaRecorder && state.isRecording) {
        state.mediaRecorder.stop();
        state.isRecording = false;

        // 更新 UI
        elements.recordBtn.classList.remove('recording');
        elements.recordingIndicator.classList.remove('active');
    }
}

// Blob 转 Base64
function blobToBase64(blob) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onloadend = () => {
            const base64 = reader.result.split(',')[1];
            resolve(base64);
        };
        reader.onerror = reject;
        reader.readAsDataURL(blob);
    });
}

// 绑定事件
function bindEvents() {
    // 发送按钮
    elements.sendBtn.addEventListener('click', sendMessage);

    // 输入框回车发送
    elements.textInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // 录音按钮
    elements.recordBtn.addEventListener('click', () => {
        if (state.isRecording) {
            stopRecording();
        } else {
            startRecording();
        }
    });

    // 停止录音按钮
    elements.stopRecordBtn.addEventListener('click', stopRecording);

    // 新对话按钮
    elements.newChatBtn.addEventListener('click', () => {
        state.conversationId = null;
        elements.messages.innerHTML = '';
        elements.welcomeScreen.style.display = 'flex';
        elements.textInput.focus();
    });

    // 设置按钮
    elements.settingsBtn.addEventListener('click', () => {
        elements.settingsModal.classList.add('active');
    });

    // 关闭设置
    elements.closeSettings.addEventListener('click', () => {
        elements.settingsModal.classList.remove('active');
    });

    // 点击遮罩关闭
    elements.settingsModal.addEventListener('click', (e) => {
        if (e.target === elements.settingsModal) {
            elements.settingsModal.classList.remove('active');
        }
    });

    // 温度滑块
    elements.settingTemperature.addEventListener('input', (e) => {
        elements.tempValue.textContent = e.target.value;
    });

    // 保存设置
    elements.saveSettings.addEventListener('click', async () => {
        const newConfig = {
            llm: {
                model: elements.settingModel.value,
                temperature: parseFloat(elements.settingTemperature.value),
                max_tokens: parseInt(elements.settingMaxTokens.value)
            },
            audio: {
                edge_tts_voice: elements.settingTtsVoice.value
            },
            asr: {
                use_local: elements.settingUseLocalAsr.checked
            }
        };

        try {
            const response = await fetch('/api/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(newConfig)
            });

            const data = await response.json();
            if (data.success) {
                state.config = { ...state.config, ...newConfig };
                elements.settingsModal.classList.remove('active');
            } else {
                showError('保存设置失败: ' + (data.error || '未知错误'));
            }
        } catch (error) {
            logger.error('[WebUI] 保存设置失败:', error);
            showError('保存设置失败');
        }
    });

    // 重置设置
    elements.resetSettings.addEventListener('click', () => {
        loadConfig();
    });

    // 快捷操作
    elements.quickActions.forEach(btn => {
        btn.addEventListener('click', () => {
            const text = btn.dataset.text;
            elements.textInput.value = text;
            sendMessage();
        });
    });

    // 设置面板中的模型选择（带搜索的 datalist）
    if (elements.settingModel) {
        // 阻止在设置面板中按回车键触发发送消息
        elements.settingModel.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                e.stopPropagation();
            }
        });

        elements.settingModel.addEventListener('change', async () => {
            const model = elements.settingModel.value;
            if (!model) return;
            try {
                await fetch('/api/config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ llm: { model } })
                });
                state.config.llm.model = model;
            } catch (error) {
                logger.error('[WebUI] 切换模型失败:', error);
            }
        });
    }
}

// 自动调整输入框高度
function autoResizeTextarea() {
    elements.textInput.addEventListener('input', () => {
        elements.textInput.style.height = 'auto';
        elements.textInput.style.height = Math.min(elements.textInput.scrollHeight, 200) + 'px';
    });
}

// HTML 转义
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 启动
init();
