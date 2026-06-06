/**
 * Voice Assistant Web UI - 主入口
 * ES Module 版本
 */

import { state, elements, logger, vadConfig } from './state.js';
import * as api from './api.js';
import * as ws from './ws.js';
import * as audio from './audio.js';
import * as ui from './ui.js';
import { showConfigPage, initConfigPage } from './config.js';
import { autoResizeTextarea } from './utils.js';

// 将 handleConfirm 挂载到 window 供内联事件使用
window.handleConfirm = function(confirmId, approved) {
    const overlay = document.querySelector('.confirm-overlay');
    if (overlay) overlay.remove();
    ws.handleConfirmResponse(confirmId, approved);
};

/**
 * 初始化应用
 */
async function init() {
    logger.info('[WebUI] 初始化...');

    await loadConfig();
    await loadModels();
    await loadHistory();
    ws.connectWebSocket();
    bindEvents();
    autoResizeTextarea(elements.textInput);
    initConfigPage();
}

/**
 * 加载配置
 */
async function loadConfig() {
    try {
        const config = await api.loadConfig();
        state.config = config;
        // VAD 配置同步
        const vadEnabled = config.vad?.enabled !== false;
        const vadDuration = config.vad?.silenceDuration || 1500;
        vadConfig.enabled = vadEnabled;
        vadConfig.silenceDuration = vadDuration;

        // 加载 Provider 列表
        await loadProviders();
    } catch (error) {
        console.error('[WebUI] 加载配置失败:', error);
    }
}

/**
 * 加载 Provider 列表
 */
async function loadProviders() {
    try {
        const data = await api.loadProviders();
        if (data.providers) {
            state.providers = data.providers;
            state.activeProvider = data.current_provider || null;
        }
        updateHeaderStatus();
    } catch (error) {
        console.error('[WebUI] 加载 Provider 列表失败:', error);
    }
}

/**
 * 同步首页顶部 Provider / 模型 chip
 */
function updateHeaderStatus() {
    const providerEl = document.getElementById('chip-provider');
    const providerLabel = document.getElementById('chip-provider-label');
    const modelEl = document.getElementById('chip-model');
    const modelLabel = document.getElementById('chip-model-label');
    if (!providerEl || !modelEl) return;

    const activePid = state.activeProvider;
    const provider = activePid ? state.providers?.[activePid] : null;
    const providerName = provider?.name || '未选择';
    const model = state.config?.llm?.model || '未选择';

    providerLabel.textContent = providerName;
    modelLabel.textContent = model;
    providerEl.classList.toggle('chip-warn', !activePid);
    modelEl.classList.toggle('chip-warn', !model || model === '未选择');
}
window.updateHeaderStatus = updateHeaderStatus;

/**
 * 加载模型列表
 */
async function loadModels() {
    try {
        await api.loadModels();
    } catch (error) {
        console.error('[WebUI] 加载模型列表失败:', error);
        state.models = [state.config.llm?.model || 'qwen-turbo'];
    }
}

/**
 * 加载历史记录
 */
async function loadHistory() {
    try {
        const conversations = await api.loadHistory();
        ui.renderHistoryList(conversations);
    } catch (error) {
        logger.error('[WebUI] 加载历史记录失败:', error);
    }
}

/**
 * 发送消息
 */
function sendMessage() {
    const text = elements.textInput.value.trim();
    if (!text) return;

    elements.textInput.value = '';
    elements.textInput.style.height = 'auto';

    if (!state.conversationId) {
        ws.startConversation(text.slice(0, 20));
        setTimeout(() => {
            ws.sendTextMessage(text);
        }, 100);
    } else {
        ws.sendTextMessage(text);
    }

    ui.addUserMessage(text);
}

/**
 * 绑定事件
 */
function bindEvents() {
    // 发送按钮
    elements.sendBtn.addEventListener('click', sendMessage);

    // IME 组字状态追踪
    let isComposing = false;
    elements.textInput.addEventListener('compositionstart', () => { isComposing = true; });
    elements.textInput.addEventListener('compositionend', () => { isComposing = false; });

    // 输入框回车发送
    elements.textInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey && !isComposing && !e.isComposing) {
            e.preventDefault();
            sendMessage();
        }
    });

    // 录音按钮
    elements.recordBtn.addEventListener('click', () => {
        if (state.isRecording) {
            audio.stopRecording();
        } else {
            audio.startRecording().catch(error => {
                ui.showError('无法访问麦克风，请检查权限设置');
            });
        }
    });

    // 停止录音按钮
    elements.stopRecordBtn.addEventListener('click', audio.stopRecording);

    // 新对话按钮
    elements.newChatBtn.addEventListener('click', () => {
        state.conversationId = null;
        elements.messages.innerHTML = '';
        elements.welcomeScreen.style.display = 'flex';
        elements.textInput.focus();
    });

    // 批量选择按钮
    const selectModeBtn = document.getElementById('select-mode-btn');
    if (selectModeBtn) {
        selectModeBtn.addEventListener('click', () => {
            if (state.isSelectMode) {
                ui.exitSelectMode();
            } else {
                ui.enterSelectMode();
            }
        });
    }

    // 设置按钮 → 打开配置页面
    elements.settingsBtn.addEventListener('click', showConfigPage);

    // 快捷操作
    elements.quickActions.forEach(btn => {
        btn.addEventListener('click', () => {
            const text = btn.dataset.text;
            elements.textInput.value = text;
            sendMessage();
        });
    });
}

// 启动应用
init();