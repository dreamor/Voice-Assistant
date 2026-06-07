/**
 * 全局状态管理模块
 */

// VAD 配置
export const vadConfig = {
    enabled: true,                    // 启用/禁用 VAD
    silenceThreshold: 0.01,           // 静音 RMS 阈值（频域归一化）
    speechThreshold: 0.02,            // 语音 RMS 阈值（频域归一化）
    silenceDuration: 700,             // 静音持续时间触发停止 (ms)
    minSpeechDuration: 300,           // 最小语音持续时间 (ms)
};

// 生成客户端 ID
export function generateClientId() {
    return 'client_' + Math.random().toString(36).substr(2, 9);
}

// 全局状态
export const state = {
    ws: null,
    clientId: generateClientId(),
    conversationId: null,
    isRecording: false,
    mediaRecorder: null,
    vadIntervalId: null,
    silenceTimerId: null,
    audioChunks: [],
    mimeType: null,
    currentMessageDiv: null,
    config: {},
    models: [],
    modelsInfo: {},
    modelsError: null,
    providers: {},
    activeProvider: null,
    reconnectTimerId: null,
    // VAD 相关状态
    vadRecordingStarted: false,
    preBufferChunks: [],
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
    },
    // 批量选择状态
    selectedConversationIds: new Set(),
    isSelectMode: false,
};

// DOM 元素引用
export const elements = {
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
    audioPlayer: document.getElementById('audio-player'),
    quickActions: document.querySelectorAll('.quick-action')
};

// 日志工具
export const logger = {
    debug: (...args) => console.debug('[WebUI]', ...args),
    info: (...args) => console.info('[WebUI]', ...args),
    warn: (...args) => console.warn('[WebUI]', ...args),
    error: (...args) => console.error('[WebUI]', ...args)
};
