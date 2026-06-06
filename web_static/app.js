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

// VAD 配置
const vadConfig = {
    enabled: true,                    // 启用/禁用 VAD
    silenceThreshold: 0.01,           // 静音 RMS 阈值
    speechThreshold: 0.02,            // 语音 RMS 阈值
    silenceDuration: 1500,            // 静音持续时间触发停止 (ms)
    minSpeechDuration: 500,           // 最小语音持续时间 (ms)
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
    models: [],
    modelsInfo: {},
    // VAD 状态
    vad: {
        audioContext: null,
        analyser: null,
        stream: null,
        isSpeaking: false,
        silenceStartTime: null,
        speechStartTime: null,
        speechDetected: false,
        animationFrameId: null,
    }
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
    settingVadEnabled: document.getElementById('setting-vad-enabled'),
    settingVadDuration: document.getElementById('setting-vad-duration'),
    vadDurationValue: document.getElementById('vad-duration-value'),
    vadDurationSetting: document.getElementById('vad-duration-setting'),
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
    
    // 初始化模型搜索
    initModelSearch();

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
            // 语音识别完成，直接上屏并发送
            hideThinking();
            const recognizedText = data.content?.trim();

            if (recognizedText) {
                // 显示用户消息在聊天界面
                addUserMessage(recognizedText);

                // 直接发送给后端
                if (!state.conversationId) {
                    state.ws.send(JSON.stringify({
                        type: 'start_conversation',
                        title: recognizedText.slice(0, 20)
                    }));
                    // 延迟发送，确保 WebSocket 消息顺序
                    setTimeout(() => {
                        sendTextMessage(recognizedText);
                    }, 100);
                } else {
                    sendTextMessage(recognizedText);
                }

                // 清空输入框
                elements.textInput.value = '';
            } else {
                showError('未能识别语音，请重试');
            }
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

        case 'confirm_required':
            showConfirmDialog(data);
            break;
    }
}

// 加载配置
async function loadConfig() {
    try {
        const response = await fetch('/api/config');
        state.config = await response.json();

        // 更新设置面板
        // 设置模型选择器的值
        if (elements.settingModel && state.config.llm?.model) {
            elements.settingModel.value = state.config.llm.model;
            const modelSearch = document.getElementById('setting-model-search');
            if (modelSearch) modelSearch.value = state.config.llm.model;
        }
        elements.settingTemperature.value = state.config.llm.temperature || 0.7;
        elements.tempValue.textContent = state.config.llm.temperature || 0.7;
        elements.settingMaxTokens.value = state.config.llm.max_tokens || 2000;
        elements.settingTtsVoice.value = state.config.audio.edge_tts_voice || 'zh-CN-XiaoxiaoNeural';
        elements.settingUseLocalAsr.checked = state.config.asr.use_local !== false;

        // VAD 配置
        const vadEnabled = state.config.vad?.enabled !== false;
        const vadDuration = state.config.vad?.silenceDuration || 1500;
        if (elements.settingVadEnabled) {
            elements.settingVadEnabled.checked = vadEnabled;
            vadConfig.enabled = vadEnabled;
        }
        if (elements.settingVadDuration) {
            elements.settingVadDuration.value = vadDuration;
            vadConfig.silenceDuration = vadDuration;
        }
        if (elements.vadDurationValue) {
            elements.vadDurationValue.textContent = vadDuration;
        }
        // 根据VAD开关显示/隐藏时长设置
        updateVadDurationVisibility();
    } catch (error) {
        console.error('[WebUI] 加载配置失败:', error);
    }
}

// 加载模型列表
async function loadModels() {
    try {
        const response = await fetch('/api/models');
        const data = await response.json();
        state.models = data.models || [];
        state.modelsInfo = {
            total: data.total || 0,
            language: data.language_models || 0,
            checked: data.checked || false
        };
        state.modelsError = data.error || null;

        // 更新模型选择界面
        updateModelSelector();
    } catch (error) {
        console.error('[WebUI] 加载模型列表失败:', error);
        state.models = [state.config.llm?.model || 'qwen-turbo'];
        state.modelsInfo = { total: 0, language: 0, checked: false };
        updateModelSelector();
    }
}

// 更新模型选择界面
function updateModelSelector() {
    const modelSelect = document.getElementById('setting-model');
    const modelSearch = document.getElementById('setting-model-search');
    
    if (!modelSelect) return;
    
    // 保存当前值
    const currentValue = state.config.llm?.model || '';
    
    // 按名称排序
    const sortedModels = [...state.models].sort((a, b) => a.localeCompare(b));
    
    // 清空并填充选项
    modelSelect.innerHTML = '';
    
    if (sortedModels.length === 0) {
        const option = document.createElement('option');
        option.value = '';
        option.textContent = '无可用模型';
        modelSelect.appendChild(option);
        return;
    }
    
    sortedModels.forEach(model => {
        const option = document.createElement('option');
        option.value = model;
        option.textContent = model;
        modelSelect.appendChild(option);
    });
    
    // 设置当前值
    if (currentValue && sortedModels.includes(currentValue)) {
        modelSelect.value = currentValue;
        if (modelSearch) modelSearch.value = currentValue;
    } else if (sortedModels.length > 0) {
        modelSelect.value = sortedModels[0];
        if (modelSearch) modelSearch.value = '';
    }
    
    console.log(`[WebUI] 模型列表已更新: ${sortedModels.length} 个可用`);
}

// 初始化模型搜索功能
function initModelSearch() {
    const modelSelect = document.getElementById('setting-model');
    const modelSearch = document.getElementById('setting-model-search');
    
    if (!modelSelect || !modelSearch) return;
    
    // 搜索输入时过滤选项
    modelSearch.addEventListener('input', (e) => {
        const searchValue = e.target.value.toLowerCase();
        const options = modelSelect.options;
        let firstMatch = '';
        
        for (let i = 0; i < options.length; i++) {
            const option = options[i];
            const match = option.value.toLowerCase().includes(searchValue);
            option.style.display = match ? '' : 'none';
            if (match && !firstMatch) firstMatch = option.value;
        }
        
        // 设置第一个匹配项为选中
        if (firstMatch && searchValue) {
            modelSelect.value = firstMatch;
        }
    });
    
    // 选择变化时更新搜索框
    modelSelect.addEventListener('change', (e) => {
        modelSearch.value = e.target.value;
    });
    
    // 点击搜索框时展开下拉
    modelSearch.addEventListener('focus', () => {
        modelSelect.size = Math.min(10, modelSelect.options.length);
        modelSelect.focus();
    });
    
    modelSelect.addEventListener('blur', () => {
        modelSelect.size = 1;
    });
    
    modelSelect.addEventListener('change', () => {
        modelSelect.size = 1;
    });
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

        // 标记是否已开始收集音频（VAD 检测到语音后才开始）
        state.vadRecordingStarted = false;
        // 缓存：VAD 检测到语音前最近 200ms 的音频数据（预缓冲）
        state.preBufferChunks = [];
        const PREBUFFER_DURATION = 200; // 预缓冲 200ms

        state.mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                if (state.vadRecordingStarted) {
                    // VAD 已检测到语音，正常收集音频
                    state.audioChunks.push(event.data);
                } else {
                    // VAD 还未检测到语音，存入预缓冲
                    state.preBufferChunks.push(event.data);
                    // 只保留最近 200ms 的数据（约 2 个 chunk）
                    const maxChunks = Math.ceil(PREBUFFER_DURATION / 100) + 1;
                    if (state.preBufferChunks.length > maxChunks) {
                        state.preBufferChunks.shift();
                    }
                }
            }
        };

        state.mediaRecorder.onstop = async () => {
            const audioBlob = new Blob(state.audioChunks, { type: state.mimeType || 'audio/webm' });
            const base64Audio = await blobToBase64(audioBlob);

            logger.info('[WebUI] 录音完成, 大小:', audioBlob.size, 'bytes, 格式:', state.mimeType);

            // 清理预缓冲
            state.preBufferChunks = [];

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

        // 每 100ms 收集一次数据
        state.mediaRecorder.start(100);
        state.isRecording = true;

        // 初始化 VAD（使用同一个音频流）
        initVAD(stream);

        // 更新 UI
        elements.recordBtn.classList.add('recording');
        elements.recordingIndicator.classList.add('active');
        updateRecordingIndicator('listening');

    } catch (error) {
        console.error('[WebUI] 录音失败:', error);
        showError('无法访问麦克风，请检查权限设置');
    }
}

// 停止录音
function stopRecording() {
    if (state.mediaRecorder && state.isRecording) {
        // 清理 VAD
        cleanupVAD();

        state.mediaRecorder.stop();
        state.isRecording = false;

        // 更新 UI
        elements.recordBtn.classList.remove('recording');
        elements.recordingIndicator.classList.remove('active');
        elements.recordingIndicator.classList.remove('vad-listening', 'vad-speaking', 'vad-silence');
    }
}

// ==================== VAD 函数 ====================

/**
 * 初始化 VAD 音频分析
 * @param {MediaStream} stream - MediaStream 音频流
 */
function initVAD(stream) {
    if (!vadConfig.enabled) return;

    try {
        state.vad.stream = stream;
        state.vad.audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const source = state.vad.audioContext.createMediaStreamSource(stream);

        state.vad.analyser = state.vad.audioContext.createAnalyser();
        state.vad.analyser.fftSize = 2048;
        state.vad.analyser.smoothingTimeConstant = 0.8;

        source.connect(state.vad.analyser);

        // 重置 VAD 状态
        state.vad.isSpeaking = false;
        state.vad.silenceStartTime = null;
        state.vad.speechStartTime = null;
        state.vad.speechDetected = false;

        // 开始分析循环
        analyzeAudio();

        console.log('[WebUI] VAD 初始化成功');
    } catch (error) {
        console.error('[WebUI] VAD 初始化失败:', error);
    }
}

/**
 * 分析音频电平进行 VAD 检测
 */
function analyzeAudio() {
    if (!state.isRecording || !state.vad.analyser) return;

    const dataArray = new Float32Array(state.vad.analyser.fftSize);
    state.vad.analyser.getFloatTimeDomainData(dataArray);

    // 计算 RMS (均方根) 音量电平
    let sum = 0;
    for (let i = 0; i < dataArray.length; i++) {
        sum += dataArray[i] * dataArray[i];
    }
    const rms = Math.sqrt(sum / dataArray.length);

    const now = Date.now();

    // 语音检测逻辑
    if (rms > vadConfig.speechThreshold) {
        // 检测到语音
        if (!state.vad.isSpeaking) {
            // 语音开始 - 将预缓冲的音频添加到正式录音
            if (!state.vadRecordingStarted && state.preBufferChunks && state.preBufferChunks.length > 0) {
                // 将预缓冲数据添加到 audioChunks
                state.audioChunks = [...state.preBufferChunks, ...state.audioChunks];
                state.preBufferChunks = [];
                console.log('[WebUI] VAD: 添加预缓冲音频', state.audioChunks.length, '个块');
            }
            state.vadRecordingStarted = true;
            state.vad.isSpeaking = true;
            state.vad.speechStartTime = now;
            state.vad.speechDetected = true;
            updateRecordingIndicator('speaking');
            console.log('[WebUI] VAD: 检测到语音开始');
        }
        state.vad.silenceStartTime = null;
    } else if (state.vad.isSpeaking) {
        // 语音后的静音
        if (!state.vad.silenceStartTime) {
            state.vad.silenceStartTime = now;
            updateRecordingIndicator('silence');
        } else if (now - state.vad.silenceStartTime >= vadConfig.silenceDuration) {
            // 静音时长超过阈值，停止录音
            const speechDuration = now - state.vad.speechStartTime;
            if (speechDuration >= vadConfig.minSpeechDuration) {
                console.log('[WebUI] VAD: 检测到语音结束，自动停止录音');
                stopRecording();
                return;
            } else {
                // 语音时长太短，重置
                state.vad.isSpeaking = false;
                state.vad.silenceStartTime = null;
                updateRecordingIndicator('listening');
            }
        }
    } else if (!state.vad.speechDetected) {
        // 还在等待语音
        updateRecordingIndicator('listening');
    }

    // 继续分析循环
    state.vad.animationFrameId = requestAnimationFrame(analyzeAudio);
}

/**
 * 更新录音指示器状态
 * @param {string} status - 'listening' | 'speaking' | 'silence'
 */
function updateRecordingIndicator(status) {
    const indicator = elements.recordingIndicator;
    if (!indicator) return;

    // 移除所有状态类
    indicator.classList.remove('vad-listening', 'vad-speaking', 'vad-silence');

    // 添加当前状态类
    switch (status) {
        case 'listening':
            indicator.classList.add('vad-listening');
            break;
        case 'speaking':
            indicator.classList.add('vad-speaking');
            break;
        case 'silence':
            indicator.classList.add('vad-silence');
            break;
    }
}

/**
 * 清理 VAD 资源
 */
function cleanupVAD() {
    if (state.vad.animationFrameId) {
        cancelAnimationFrame(state.vad.animationFrameId);
        state.vad.animationFrameId = null;
    }

    if (state.vad.audioContext) {
        state.vad.audioContext.close().catch(() => {});
        state.vad.audioContext = null;
    }

    state.vad.analyser = null;
    state.vad.stream = null;
    state.vad.isSpeaking = false;
    state.vad.silenceStartTime = null;
    state.vad.speechStartTime = null;
    state.vad.speechDetected = false;
    
    // 清理录音相关状态
    state.vadRecordingStarted = false;
    state.preBufferChunks = [];

    updateRecordingIndicator('listening');
}

/**
 * 更新 VAD 时长设置的可见性
 */
function updateVadDurationVisibility() {
    if (elements.vadDurationSetting) {
        elements.vadDurationSetting.style.display = vadConfig.enabled ? 'flex' : 'none';
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

    // IME 组字状态追踪
    let isComposing = false;
    elements.textInput.addEventListener('compositionstart', () => { isComposing = true; });
    elements.textInput.addEventListener('compositionend', () => { isComposing = false; });

    // 输入框回车发送（排除 IME 组字状态）
    elements.textInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey && !isComposing && !e.isComposing) {
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
        const temperature = parseFloat(elements.settingTemperature.value);
        const maxTokens = parseInt(elements.settingMaxTokens.value);
        
        const newConfig = {
            llm: {
                model: elements.settingModel.value || state.config.llm.model,
                temperature: !isNaN(temperature) ? temperature : 0.7,
                max_tokens: !isNaN(maxTokens) ? maxTokens : 2000
            },
            audio: {
                edge_tts_voice: elements.settingTtsVoice.value || 'zh-CN-XiaoxiaoNeural'
            }
        };

        try {
            const response = await fetch('/api/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(newConfig)
            });

            if (!response.ok) {
                const errorData = await response.json();
                showError('保存设置失败: ' + (errorData.detail || '服务器错误'));
                return;
            }

            const data = await response.json();
            if (data.success) {
                state.config = { ...state.config, ...newConfig };
                // 更新本地 VAD 配置
                if (elements.settingVadEnabled) {
                    vadConfig.enabled = elements.settingVadEnabled.checked;
                }
                if (elements.settingVadDuration) {
                    vadConfig.silenceDuration = parseInt(elements.settingVadDuration.value) || 1500;
                }
                elements.settingsModal.classList.remove('active');
            } else {
                showError('保存设置失败: ' + (data.error || '未知错误'));
            }
        } catch (error) {
            console.error('[WebUI] 保存设置失败:', error);
            showError('保存设置失败: ' + error.message);
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
                const response = await fetch('/api/config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ llm: { model: model } })
                });
                const data = await response.json();
                if (data.success) {
                    state.config.llm.model = model;
                    console.log('[WebUI] 模型已切换为:', model);
                } else {
                    console.error('[WebUI] 切换模型失败:', data.error);
                }
            } catch (error) {
                console.error('[WebUI] 切换模型失败:', error);
            }
        });
    }

    // VAD 开关
    if (elements.settingVadEnabled) {
        elements.settingVadEnabled.addEventListener('change', (e) => {
            vadConfig.enabled = e.target.checked;
            updateVadDurationVisibility();
        });
    }

    // VAD 静音检测时长
    if (elements.settingVadDuration) {
        elements.settingVadDuration.addEventListener('input', (e) => {
            const value = parseInt(e.target.value);
            vadConfig.silenceDuration = value;
            if (elements.vadDurationValue) {
                elements.vadDurationValue.textContent = value;
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

// 确认弹窗状态（用于倒计时 / 标题闪烁 / 提示音）
const _confirmState = {
    countdownTimer: null,
    titleFlashTimer: null,
    audioCtx: null,
    originalTitle: null,
};

// 启动倒计时 + 标题闪烁 + 提示音
function _startConfirmAlerts(overlay, secondsLeft) {
    const countdownEl = overlay.querySelector('.confirm-countdown');
    const titlePrefix = '[待确认] ';

    // 保存原始标题
    if (_confirmState.originalTitle === null) {
        _confirmState.originalTitle = document.title;
    }
    document.title = titlePrefix + _confirmState.originalTitle;

    // 标题闪烁（每 1s 切换一次）
    let flashOn = true;
    _confirmState.titleFlashTimer = setInterval(() => {
        flashOn = !flashOn;
        document.title = (flashOn ? titlePrefix : '🔔 ') + _confirmState.originalTitle;
    }, 1000);

    // 提示音（用 Web Audio API 生成短促哔声，每 2s 一次，不依赖音频文件）
    try {
        if (!_confirmState.audioCtx) {
            _confirmState.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        }
        const ctx = _confirmState.audioCtx;
        const beep = () => {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.frequency.value = 880;
            osc.type = 'sine';
            gain.gain.setValueAtTime(0, ctx.currentTime);
            gain.gain.linearRampToValueAtTime(0.15, ctx.currentTime + 0.01);
            gain.gain.linearRampToValueAtTime(0, ctx.currentTime + 0.15);
            osc.start(ctx.currentTime);
            osc.stop(ctx.currentTime + 0.15);
        };
        beep();
        _confirmState.beepTimer = setInterval(beep, 2000);
    } catch (e) {
        console.warn('AudioContext 不可用，跳过提示音:', e);
    }

    // 倒计时
    _confirmState.countdownTimer = setInterval(() => {
        secondsLeft -= 1;
        if (countdownEl) {
            countdownEl.textContent = secondsLeft;
            countdownEl.classList.toggle('countdown-urgent', secondsLeft <= 10);
        }
        if (secondsLeft <= 0) {
            clearInterval(_confirmState.countdownTimer);
            _confirmState.countdownTimer = null;
        }
    }, 1000);
}

// 清理倒计时 / 标题 / 提示音
function _stopConfirmAlerts() {
    if (_confirmState.countdownTimer) {
        clearInterval(_confirmState.countdownTimer);
        _confirmState.countdownTimer = null;
    }
    if (_confirmState.titleFlashTimer) {
        clearInterval(_confirmState.titleFlashTimer);
        _confirmState.titleFlashTimer = null;
    }
    if (_confirmState.beepTimer) {
        clearInterval(_confirmState.beepTimer);
        _confirmState.beepTimer = null;
    }
    if (_confirmState.originalTitle !== null) {
        document.title = _confirmState.originalTitle;
    }
}

// 确认弹窗：显示需要用户确认的操作
function showConfirmDialog(data) {
    const { confirm_id, tool_name, arguments: args, message, level, timeout } = data;
    const seconds = Number(timeout) || 60;

    // 先关掉旧的弹窗和计时器
    _stopConfirmAlerts();
    const old = document.querySelector('.confirm-overlay');
    if (old) old.remove();

    const overlay = document.createElement('div');
    overlay.className = 'confirm-overlay';

    const levelLabel = level === 'double_confirm' ? '⚠️ 危险操作' : '🔒 需要确认';
    const levelClass = level === 'double_confirm' ? 'confirm-danger' : 'confirm-warning';

    const argsText = Object.entries(args || {})
        .map(([k, v]) => `${k}: ${v}`)
        .join('\n');

    overlay.innerHTML = `
        <div class="confirm-dialog ${levelClass}">
            <div class="confirm-header">${levelLabel} <span class="confirm-countdown-wrap">⏱ <span class="confirm-countdown">${seconds}</span>s</span></div>
            <div class="confirm-tool-name">${escapeHtml(tool_name)}</div>
            <div class="confirm-message">${escapeHtml(message)}</div>
            ${argsText ? `<pre class="confirm-args">${escapeHtml(argsText)}</pre>` : ''}
            <div class="confirm-actions">
                <button class="confirm-btn confirm-reject" onclick="handleConfirm('${confirm_id}', false)">拒绝</button>
                <button class="confirm-btn confirm-approve" onclick="handleConfirm('${confirm_id}', true)">确认执行</button>
            </div>
        </div>
    `;

    document.body.appendChild(overlay);
    _startConfirmAlerts(overlay, seconds);
}

// 处理确认/拒绝
function handleConfirm(confirmId, approved) {
    _stopConfirmAlerts();
    const overlay = document.querySelector('.confirm-overlay');
    if (overlay) overlay.remove();

    if (state.ws && state.ws.readyState === WebSocket.OPEN) {
        state.ws.send(JSON.stringify({
            type: 'confirm_response',
            confirm_id: confirmId,
            approved: approved
        }));
    }
}

// 启动
init();
