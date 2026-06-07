/**
 * UI 渲染和交互模块
 */

import { state, elements, vadConfig } from './state.js';
import * as api from './api.js';
import * as ws from './ws.js';
import * as audio from './audio.js';
import { escapeHtml, formatMessageContent, autoResizeTextarea } from './utils.js';

/**
 * 初始化模型搜索功能（配置已迁移到独立页面，此函数保留为空操作）
 */
export function initModelSearch() {
    // No-op: model selection is now in the config page
}

/**
 * 渲染历史记录列表
 * @param {Array} conversations - 对话列表
 */
export function renderHistoryList(conversations) {
    const isSelect = state.isSelectMode;

    elements.historyList.innerHTML = conversations.map(conv => `
        <div class="history-item ${conv.id === state.conversationId ? 'active' : ''} ${state.selectedConversationIds.has(conv.id) ? 'selected' : ''}" data-id="${conv.id}">
            ${isSelect ? `<input type="checkbox" class="history-checkbox" data-id="${conv.id}" ${state.selectedConversationIds.has(conv.id) ? 'checked' : ''} />` : ''}
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
            </svg>
            <span>${escapeHtml(conv.title)}</span>
            ${!isSelect ? `<button class="btn-icon delete-btn" data-id="${conv.id}" title="删除">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
            </button>` : ''}
        </div>
    `).join('');

    // 绑定事件
    document.querySelectorAll('.history-item').forEach(item => {
        item.addEventListener('click', (e) => {
            if (e.target.closest('.delete-btn')) return;
            if (e.target.closest('.history-checkbox')) return;
            const id = item.dataset.id;

            if (state.isSelectMode) {
                toggleConversationSelection(id);
            } else {
                loadConversation(id);
            }
        });
    });

    // 复选框事件
    document.querySelectorAll('.history-checkbox').forEach(cb => {
        cb.addEventListener('change', (e) => {
            const id = cb.dataset.id;
            toggleConversationSelection(id);
        });
    });

    // 单个删除按钮
    document.querySelectorAll('.delete-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            handleDeleteConversation(btn.dataset.id);
        });
    });

    // 更新批量操作栏
    updateBatchActionBar();
}

/**
 * 切换对话选中状态
 * @param {string} id - 对话 ID
 */
function toggleConversationSelection(id) {
    if (state.selectedConversationIds.has(id)) {
        state.selectedConversationIds.delete(id);
    } else {
        state.selectedConversationIds.add(id);
    }

    // 更新 UI
    const item = document.querySelector(`.history-item[data-id="${id}"]`);
    const checkbox = document.querySelector(`.history-checkbox[data-id="${id}"]`);
    if (item) item.classList.toggle('selected', state.selectedConversationIds.has(id));
    if (checkbox) checkbox.checked = state.selectedConversationIds.has(id);

    updateBatchActionBar();
}

/**
 * 更新批量操作栏
 */
function updateBatchActionBar() {
    let actionBar = document.getElementById('batch-action-bar');
    const selectMode = state.isSelectMode;

    if (!selectMode) {
        if (actionBar) actionBar.remove();
        return;
    }

    const count = state.selectedConversationIds.size;

    if (!actionBar) {
        actionBar = document.createElement('div');
        actionBar.id = 'batch-action-bar';
        actionBar.className = 'batch-action-bar';
        const sidebar = document.querySelector('.sidebar');
        sidebar.appendChild(actionBar);
    }

    actionBar.innerHTML = `
        <button class="batch-btn select-all-btn" id="batch-select-all">${count > 0 ? '取消全选' : '全选'}</button>
        <span class="batch-count">${count > 0 ? `已选 ${count} 项` : '未选择'}</span>
        <button class="batch-btn batch-delete-btn" ${count === 0 ? 'disabled' : ''}>删除选中</button>
        <button class="batch-btn cancel-btn">取消</button>
    `;

    actionBar.querySelector('#batch-select-all').addEventListener('click', handleSelectAll);
    actionBar.querySelector('.batch-delete-btn').addEventListener('click', handleBatchDelete);
    actionBar.querySelector('.cancel-btn').addEventListener('click', exitSelectMode);
}

/**
 * 进入选择模式
 */
export function enterSelectMode() {
    state.isSelectMode = true;
    state.selectedConversationIds.clear();

    const selectBtn = document.getElementById('select-mode-btn');
    if (selectBtn) selectBtn.classList.add('active');

    // 重新渲染列表，让 renderHistoryList 统一处理 checkbox DOM 与 change 绑定
    api.loadHistory().then(renderHistoryList);
}

/**
 * 退出选择模式
 */
export function exitSelectMode() {
    state.isSelectMode = false;
    state.selectedConversationIds.clear();

    const selectBtn = document.getElementById('select-mode-btn');
    if (selectBtn) selectBtn.classList.remove('active');

    // 移除操作栏
    const actionBar = document.getElementById('batch-action-bar');
    if (actionBar) actionBar.remove();

    // 重新渲染历史列表
    api.loadHistory().then(renderHistoryList);
}

/**
 * 全选/取消全选
 */
function handleSelectAll() {
    const allIds = [...document.querySelectorAll('.history-item')].map(item => item.dataset.id);

    if (state.selectedConversationIds.size === allIds.length && allIds.length > 0) {
        state.selectedConversationIds.clear();
    } else {
        state.selectedConversationIds = new Set(allIds);
    }

    // 更新所有复选框和项样式
    document.querySelectorAll('.history-checkbox').forEach(cb => {
        cb.checked = state.selectedConversationIds.has(cb.dataset.id);
    });
    document.querySelectorAll('.history-item').forEach(item => {
        item.classList.toggle('selected', state.selectedConversationIds.has(item.dataset.id));
    });

    updateBatchActionBar();
}

/**
 * 批量删除
 */
async function handleBatchDelete() {
    const ids = [...state.selectedConversationIds];
    if (ids.length === 0) return;

    if (!confirm(`确定要删除 ${ids.length} 个对话吗？`)) return;

    try {
        const result = await api.batchDeleteConversations(ids);
        if (result.deleted > 0) {
            // 如果当前对话被删除，清空消息区
            if (ids.includes(state.conversationId)) {
                state.conversationId = null;
                elements.messages.innerHTML = '';
                elements.welcomeScreen.style.display = 'flex';
            }
            // exitSelectMode 内部会重新 fetch 并渲染
            exitSelectMode();
        }
    } catch (error) {
        showError('批量删除失败');
    }
}

/**
 * 加载指定对话
 * @param {string} id - 对话 ID
 */
export async function loadConversation(id) {
    try {
        const data = await api.loadConversation(id);
        state.conversationId = id;

        elements.welcomeScreen.style.display = 'none';
        elements.messages.innerHTML = '';
        data.messages.forEach(msg => {
            if (msg.role === 'user') {
                addUserMessage(msg.content, false);
            } else {
                addAssistantMessage(msg.content, false);
            }
        });

        document.querySelectorAll('.history-item').forEach(item => {
            item.classList.toggle('active', item.dataset.id === id);
        });

        scrollToBottom();
    } catch (error) {
        showError('加载对话失败');
    }
}

/**
 * 加载对话消息（WebSocket 回调用）
 * @param {string} id - 对话 ID
 */
export async function loadConversationMessages(id) {
    try {
        const data = await api.loadConversation(id);
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
        console.error('[WebUI] 加载消息失败:', error);
    }
}

/**
 * 处理删除对话
 * @param {string} id - 对话 ID
 */
async function handleDeleteConversation(id) {
    if (!confirm('确定要删除这个对话吗？')) return;

    try {
        const data = await api.deleteConversation(id);
        if (data.success) {
            if (state.conversationId === id) {
                state.conversationId = null;
                elements.messages.innerHTML = '';
                elements.welcomeScreen.style.display = 'flex';
            }
            const conversations = await api.loadHistory();
            renderHistoryList(conversations);
        }
    } catch (error) {
        showError('删除对话失败');
    }
}

/**
 * 添加用户消息
 * @param {string} content - 消息内容
 * @param {boolean} animate - 是否动画
 */
export function addUserMessage(content, animate = true) {
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

/**
 * 开始流式消息
 * @returns {HTMLElement} 消息元素
 */
export function startStreamingMessage() {
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

    messageDiv.querySelector('.copy-btn').addEventListener('click', () => {
        const text = messageDiv.querySelector('.streaming-text').textContent;
        navigator.clipboard.writeText(text);
    });

    messageDiv.querySelector('.replay-btn').addEventListener('click', () => {
        const text = messageDiv.querySelector('.streaming-text').textContent;
        ws.replayTTS(text);
    });

    return messageDiv;
}

/**
 * 更新流式消息
 * @param {string} content - 内容
 */
export function updateStreamingMessage(content) {
    if (!state.currentMessageDiv) {
        startStreamingMessage();
    }

    const textSpan = state.currentMessageDiv.querySelector('.streaming-text');
    // 累加增量 token（后端每次只推送 delta，前端负责拼接）
    const prev = textSpan.dataset.raw || '';
    const next = prev + (content || '');
    textSpan.dataset.raw = next;
    textSpan.innerHTML = formatMessageContent(next);
    scrollToBottom();
}

/**
 * 完成流式消息
 * @param {string} content - 内容
 */
export function finalizeStreamingMessage(content) {
    if (state.currentMessageDiv) {
        const cursor = state.currentMessageDiv.querySelector('.streaming-cursor');
        if (cursor) cursor.remove();
        state.currentMessageDiv = null;
    } else if (content) {
        // 如果没有流式消息容器但有内容，创建完整消息
        addAssistantMessage(content);
    }
    scrollToBottom();
}

/**
 * 添加 AI 消息（非流式）
 * @param {string} content - 内容
 * @param {boolean} animate - 是否动画
 */
export function addAssistantMessage(content, animate = true) {
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

    messageDiv.querySelector('.copy-btn').addEventListener('click', () => {
        navigator.clipboard.writeText(content);
    });

    messageDiv.querySelector('.replay-btn').addEventListener('click', () => {
        ws.replayTTS(content);
    });
}

/**
 * 显示思考中
 * @param {string} text - 提示文本
 */
export function showThinking(text) {
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

/**
 * 更新思考中提示文字（不重建 DOM，避免闪烁）
 * @param {string} text - 新提示文本
 */
export function updateThinkingText(text) {
    const thinkingDiv = document.getElementById('thinking-indicator');
    if (thinkingDiv) {
        const span = thinkingDiv.querySelector('.thinking-indicator > span:last-child');
        if (span) span.textContent = text;
    } else {
        showThinking(text);
    }
}

/**
 * 隐藏思考中
 */
export function hideThinking() {
    const thinkingDiv = document.getElementById('thinking-indicator');
    if (thinkingDiv) {
        thinkingDiv.remove();
    }
}

/**
 * 显示错误
 * @param {string} message - 错误消息
 */
export function showError(message) {
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

/**
 * 播放音频
 * @param {string} base64Data - Base64 编码的音频
 */
export function playAudio(base64Data) {
    audio.playAudio(base64Data);
}

/**
 * 播放音频块（流式TTS）
 * @param {string} base64Data - Base64 编码的音频
 * @param {number} chunkIndex - 块索引
 */
export function playAudioChunk(base64Data, chunkIndex) {
    audio.playAudioChunk(base64Data, chunkIndex);
}

/**
 * 完成流式音频播放
 */
export function finalizeAudioPlayback() {
    audio.finalizeAudioPlayback();
}

/**
 * 滚动到底部
 */
export function scrollToBottom() {
    elements.messagesContainer.scrollTop = elements.messagesContainer.scrollHeight;
}

/**
 * 显示工具调用信息
 * @param {string} toolName - 工具名称
 * @param {Object} arguments - 工具参数
 * @param {string} callId - 调用 ID
 */
export function showToolCall(toolName, args, callId) {
    const callDiv = document.createElement('div');
    callDiv.className = 'message assistant tool-call-msg';
    callDiv.dataset.callId = callId || '';

    const argsText = args && Object.keys(args).length > 0
        ? Object.entries(args).map(([k, v]) => `${k}: ${typeof v === 'string' ? v : JSON.stringify(v)}`).join(', ')
        : '';

    callDiv.innerHTML = `
        <div class="message-avatar">🔧</div>
        <div class="message-content">
            <div class="tool-call-header">
                <span class="tool-call-name">${escapeHtml(toolName)}</span>
                <span class="tool-call-status">执行中...</span>
            </div>
            ${argsText ? `<div class="tool-call-args">${escapeHtml(argsText)}</div>` : ''}
        </div>
    `;

    elements.messages.appendChild(callDiv);
    scrollToBottom();
}

/**
 * 显示工具执行结果
 * @param {Object} data - 工具结果数据
 * @param {string} data.toolName - 工具名称
 * @param {string} data.toolCallId - 调用 ID
 * @param {boolean} data.success - 是否成功
 * @param {string} data.message - 结果消息
 * @param {Object} data.data - 结构化数据
 * @param {string} data.displayHint - 渲染提示
 * @param {number} data.durationMs - 执行耗时
 */
export function showToolResult(data) {
    const { toolName, toolCallId, success, message, displayHint, durationMs } = data;

    // 尝试匹配已有的 tool-call 消息并更新
    const callDiv = toolCallId
        ? document.querySelector(`.tool-call-msg[data-call-id="${toolCallId}"]`)
        : null;

    if (callDiv) {
        const statusEl = callDiv.querySelector('.tool-call-status');
        if (statusEl) {
            statusEl.textContent = success ? '✓ 完成' : '✗ 失败';
            statusEl.className = `tool-call-status ${success ? 'tool-status-ok' : 'tool-status-err'}`;
        }
        if (durationMs != null) {
            const durEl = document.createElement('span');
            durEl.className = 'tool-call-duration';
            durEl.textContent = `${durationMs}ms`;
            callDiv.querySelector('.tool-call-header').appendChild(durEl);
        }
        const resultEl = document.createElement('div');
        resultEl.className = `tool-result ${success ? 'tool-result-ok' : 'tool-result-err'}`;
        resultEl.innerHTML = renderToolContent(message, data.data, displayHint);
        callDiv.querySelector('.message-content').appendChild(resultEl);
        return;
    }

    // 没有匹配的 tool-call，独立显示结果
    const resultDiv = document.createElement('div');
    resultDiv.className = `message assistant tool-result-msg ${success ? 'tool-result-ok' : 'tool-result-err'}`;
    resultDiv.innerHTML = `
        <div class="message-avatar">${success ? '✓' : '✗'}</div>
        <div class="message-content">
            <div class="tool-result-header">${escapeHtml(toolName || '工具')}</div>
            <div class="tool-result-body">${renderToolContent(message, data.data, displayHint)}</div>
        </div>
    `;
    elements.messages.appendChild(resultDiv);
    scrollToBottom();
}

/**
 * 根据 displayHint 渲染工具结果内容
 * @param {string} message - 结果文本
 * @param {Object} data - 结构化数据
 * @param {string} hint - 渲染提示
 * @returns {string} HTML 内容
 */
function renderToolContent(message, data, hint) {
    if (!hint || hint === 'text') {
        return `<p>${escapeHtml(message || '')}</p>`;
    }
    if (hint === 'code') {
        const lang = data?.language || '';
        return `<pre><code class="language-${lang}">${escapeHtml(message || '')}</code></pre>`;
    }
    if (hint === 'table' && data?.headers && data?.rows) {
        const hdr = data.headers.map(h => `<th>${escapeHtml(h)}</th>`).join('');
        const rows = data.rows.map(r =>
            `<tr>${r.map(c => `<td>${escapeHtml(String(c))}</td>`).join('')}</tr>`
        ).join('');
        return `<table class="tool-result-table"><thead><tr>${hdr}</tr></thead><tbody>${rows}</tbody></table>`;
    }
    if (hint === 'image' && data?.url) {
        return `<img src="${escapeHtml(data.url)}" class="tool-result-image" alt="tool result" />`;
    }
    if (hint === 'markdown') {
        return formatMessageContent(message || '');
    }
    if (hint === 'link' && data?.url) {
        return `<a href="${escapeHtml(data.url)}" target="_blank" rel="noopener">${escapeHtml(message || data.url)}</a>`;
    }
    if (hint === 'error') {
        return `<div class="tool-result-error">${escapeHtml(message || '执行失败')}</div>`;
    }
    // 降级为纯文本
    return `<p>${escapeHtml(message || '')}</p>`;
}

/**
 * 显示确认弹窗
 * @param {Object} data - 确认数据
 */
export function showConfirmDialog(data) {
    const { confirm_id, tool_name, arguments: args, message, level } = data;

    const overlay = document.createElement('div');
    overlay.className = 'confirm-overlay';

    const levelLabel = level === 'double_confirm' ? '⚠️ 危险操作' : '🔒 需要确认';
    const levelClass = level === 'double_confirm' ? 'confirm-danger' : 'confirm-warning';

    const argsText = Object.entries(args || {})
        .map(([k, v]) => `${k}: ${v}`)
        .join('\n');

    overlay.innerHTML = `
        <div class="confirm-dialog ${levelClass}">
            <div class="confirm-header">${levelLabel}</div>
            <div class="confirm-tool-name">${escapeHtml(tool_name)}</div>
            <div class="confirm-message">${escapeHtml(message)}</div>
            ${argsText ? `<pre class="confirm-args">${escapeHtml(argsText)}</pre>` : ''}
            <div class="confirm-actions">
                <button class="confirm-btn confirm-reject" data-confirm-id="${escapeHtml(confirm_id)}" data-approved="false">拒绝</button>
                <button class="confirm-btn confirm-approve" data-confirm-id="${escapeHtml(confirm_id)}" data-approved="true">确认执行</button>
            </div>
        </div>
    `;

    overlay.querySelectorAll('.confirm-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const approved = btn.dataset.approved === 'true';
            window.handleConfirm(btn.dataset.confirmId, approved);
        });
    });

    document.body.appendChild(overlay);
}

/**
 * 更新 VAD 时长设置可见性
 */
export function updateVadDurationVisibility() {
    if (elements.vadDurationSetting) {
        elements.vadDurationSetting.style.display = vadConfig.enabled ? 'flex' : 'none';
    }
}

// 导出自动调整 textarea 函数
export { autoResizeTextarea };
