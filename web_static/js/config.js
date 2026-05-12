/**
 * Voice Assistant - 模型配置页面
 * 独立全屏配置页面，支持 Provider 选择、自定义 Provider、模型管理
 */

import { state, elements, logger, vadConfig } from './state.js';
import * as api from './api.js';

let selectedProviderId = null;
let addProviderFormVisible = false;

/**
 * 渲染配置页面
 */
export function renderConfigPage() {
    const page = document.getElementById('config-page');
    if (!page) return;

    const providers = state.providers || {};
    const currentProvider = state.activeProvider;
    const currentModel = state.config?.llm?.model || '';

    // 当前 Provider 信息
    const activeProvider = currentProvider ? providers[currentProvider] : null;
    const activeProviderCard = page.querySelector('.active-provider-info');
    if (activeProviderCard) {
        if (activeProvider) {
            activeProviderCard.innerHTML = `
                <div class="provider-status">
                    <span class="provider-status-name">${activeProvider.name}</span>
                    <span class="api-key-status ${activeProvider.has_key ? 'configured' : 'not-configured'}">
                        ${activeProvider.has_key ? 'API Key 已配置' : 'API Key 未配置'}
                    </span>
                </div>
                <div class="provider-status-model">当前模型: ${currentModel}</div>
            `;
        } else {
            activeProviderCard.innerHTML = '<div class="provider-status">未选择 Provider</div>';
        }
    }

    // Provider 列表
    renderProviderList(page, providers, currentProvider);

    // Provider 详情
    if (selectedProviderId && providers[selectedProviderId]) {
        renderProviderDetail(page, providers[selectedProviderId]);
    } else {
        const detailPanel = page.querySelector('.provider-detail-panel');
        if (detailPanel) detailPanel.innerHTML = '<div class="detail-empty">选择一个 Provider 查看详情</div>';
    }

    // 添加 Provider 表单
    if (addProviderFormVisible) {
        renderAddProviderForm(page);
    } else {
        const formContainer = page.querySelector('.add-provider-form-container');
        if (formContainer) formContainer.innerHTML = '';
    }

    // 通用设置
    renderGeneralSettings(page);
}

/**
 * 渲染 Provider 列表
 */
function renderProviderList(page, providers, currentProvider) {
    const listEl = page.querySelector('.provider-list');
    if (!listEl) return;

    const entries = Object.entries(providers);
    if (entries.length === 0) {
        listEl.innerHTML = '<div class="list-empty">暂无 Provider</div>';
        return;
    }

    listEl.innerHTML = entries.map(([pid, p]) => `
        <div class="provider-card ${pid === currentProvider ? 'active' : ''} ${pid === selectedProviderId ? 'selected' : ''}"
             data-provider-id="${pid}">
            <div class="provider-card-header">
                <span class="provider-card-name">${p.name}</span>
                ${p.is_custom ? '<span class="provider-badge custom">自定义</span>' : '<span class="provider-badge builtin">内置</span>'}
            </div>
            <div class="provider-card-meta">
                <span class="provider-card-models">${p.models.length} 个模型</span>
                <span class="api-key-status ${p.has_key ? 'configured' : 'not-configured'}">
                    ${p.has_key ? 'Key ✓' : 'Key ✗'}
                </span>
            </div>
        </div>
    `).join('');

    // 绑定点击事件
    listEl.querySelectorAll('.provider-card').forEach(card => {
        card.addEventListener('click', () => {
            selectedProviderId = card.dataset.providerId;
            renderConfigPage();
        });
    });
}

/**
 * 渲染 Provider 详情面板
 */
function renderProviderDetail(page, provider) {
    const panel = page.querySelector('.provider-detail-panel');
    if (!panel) return;

    const pid = selectedProviderId;
    const isCustom = provider.is_custom;

    panel.innerHTML = `
        <div class="detail-header">
            <h3>${provider.name}</h3>
            <div class="detail-actions">
                ${pid === state.activeProvider ? '<span class="detail-current">当前使用</span>' : `<button class="btn-sm btn-primary" id="btn-switch-provider">切换使用</button>`}
                ${isCustom ? '<button class="btn-sm btn-danger" id="btn-delete-provider">删除</button>' : ''}
            </div>
        </div>

        <div class="detail-body">
            <div class="detail-field">
                <label>Base URL</label>
                <span class="detail-value">${provider.base_url || '未配置'}</span>
            </div>
            <div class="detail-field">
                <label>API Key</label>
                <div class="detail-api-key">
                    <input type="password" id="detail-api-key-input"
                           placeholder="${provider.has_key ? '已配置（输入可更新）' : '输入 API Key...'}"
                           autocomplete="off">
                    <button class="btn-icon" id="toggle-detail-key" title="显示/隐藏">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                            <circle cx="12" cy="12" r="3"></circle>
                        </svg>
                    </button>
                    <button class="btn-sm btn-primary" id="btn-save-api-key">保存</button>
                </div>
                <span class="api-key-status ${provider.has_key ? 'configured' : 'not-configured'}">
                    ${provider.has_key ? '已配置' : '未配置'}
                </span>
            </div>

            <div class="detail-field">
                <label>模型列表</label>
                <div class="detail-models">
                    ${provider.models.map(m => `<span class="model-tag">${m.id}</span>`).join('')}
                    ${provider.models.length === 0 ? '<span class="no-models">暂无模型</span>' : ''}
                </div>
                ${provider.base_url ? `<button class="btn-sm btn-secondary" id="btn-fetch-models">从 API 获取模型</button>` : ''}
            </div>

            ${isCustom ? `
            <div class="detail-field">
                <label>LiteLLM 前缀</label>
                <span class="detail-value">${provider.litellm_prefix || 'openai'}</span>
            </div>
            ` : ''}
        </div>
    `;

    // 绑定事件
    const switchBtn = panel.querySelector('#btn-switch-provider');
    if (switchBtn) {
        switchBtn.addEventListener('click', async () => {
            try {
                const modelId = provider.models.length > 0 ? provider.models[0].id : undefined;
                await api.switchProvider(pid, modelId);
                state.activeProvider = pid;
                state.config.llm.model = modelId || state.config.llm.model;
                renderConfigPage();
            } catch (error) {
                alert('切换失败: ' + error.message);
            }
        });
    }

    const deleteBtn = panel.querySelector('#btn-delete-provider');
    if (deleteBtn) {
        deleteBtn.addEventListener('click', async () => {
            if (!confirm(`确定删除 Provider "${provider.name}"？`)) return;
            try {
                await api.deleteProvider(pid);
                if (state.activeProvider === pid) {
                    state.activeProvider = null;
                }
                delete state.providers[pid];
                selectedProviderId = null;
                renderConfigPage();
            } catch (error) {
                alert('删除失败: ' + error.message);
            }
        });
    }

    const toggleKeyBtn = panel.querySelector('#toggle-detail-key');
    const keyInput = panel.querySelector('#detail-api-key-input');
    if (toggleKeyBtn && keyInput) {
        toggleKeyBtn.addEventListener('click', () => {
            keyInput.type = keyInput.type === 'password' ? 'text' : 'password';
        });
    }

    const saveKeyBtn = panel.querySelector('#btn-save-api-key');
    if (saveKeyBtn) {
        saveKeyBtn.addEventListener('click', async () => {
            const key = keyInput.value.trim();
            if (!key) return;
            try {
                await api.setProviderApiKey(pid, key);
                keyInput.value = '';
                if (state.providers[pid]) {
                    state.providers[pid].has_key = true;
                }
                renderConfigPage();
            } catch (error) {
                alert('保存失败: ' + error.message);
            }
        });
    }

    const fetchModelsBtn = panel.querySelector('#btn-fetch-models');
    if (fetchModelsBtn) {
        fetchModelsBtn.addEventListener('click', async () => {
            fetchModelsBtn.textContent = '获取中...';
            fetchModelsBtn.disabled = true;
            try {
                const data = await api.fetchProviderModels(pid);
                if (data.models && data.models.length > 0) {
                    // 更新 state 中的 provider 模型列表
                    if (state.providers[pid]) {
                        state.providers[pid].models = data.models;
                    }
                    renderConfigPage();
                } else {
                    alert('未获取到模型列表');
                }
            } catch (error) {
                alert('获取模型失败: ' + error.message);
            } finally {
                fetchModelsBtn.textContent = '从 API 获取模型';
                fetchModelsBtn.disabled = false;
            }
        });
    }
}

/**
 * 渲染添加自定义 Provider 表单
 */
function renderAddProviderForm(page) {
    const container = page.querySelector('.add-provider-form-container');
    if (!container) return;

    container.innerHTML = `
        <div class="add-provider-form">
            <h3>添加自定义 Provider</h3>
            <div class="form-field">
                <label>Provider ID</label>
                <input type="text" id="new-provider-id" placeholder="如 my-vllm (字母数字、-、_)" autocomplete="off">
            </div>
            <div class="form-field">
                <label>名称</label>
                <input type="text" id="new-provider-name" placeholder="如 My vLLM Server" autocomplete="off">
            </div>
            <div class="form-field">
                <label>Base URL</label>
                <input type="text" id="new-provider-base-url" placeholder="如 https://api.example.com/v1" autocomplete="off">
            </div>
            <div class="form-field">
                <label>API Key</label>
                <input type="password" id="new-provider-api-key" placeholder="可选" autocomplete="off">
            </div>
            <div class="form-field">
                <label>LiteLLM 前缀</label>
                <select id="new-provider-prefix">
                    <option value="openai">openai</option>
                    <option value="anthropic">anthropic</option>
                </select>
            </div>
            <div class="form-field">
                <label>模型列表</label>
                <div class="model-tags-input" id="new-provider-models">
                    <div class="tags-container"></div>
                    <input type="text" id="new-model-input" placeholder="输入模型 ID 后按 Enter 添加" autocomplete="off">
                </div>
            </div>
            <div class="form-actions">
                <button class="btn-secondary" id="btn-cancel-add-provider">取消</button>
                <button class="btn-primary" id="btn-submit-add-provider">创建</button>
            </div>
        </div>
    `;

    // 模型标签输入
    const tagsContainer = container.querySelector('.tags-container');
    const modelInput = container.querySelector('#new-model-input');
    const models = [];

    modelInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.isComposing) {
            e.preventDefault();
            const val = modelInput.value.trim();
            if (val && !models.includes(val)) {
                models.push(val);
                const tag = document.createElement('span');
                tag.className = 'model-tag removable';
                tag.textContent = val;
                tag.addEventListener('click', () => {
                    const idx = models.indexOf(val);
                    if (idx >= 0) models.splice(idx, 1);
                    tag.remove();
                });
                tagsContainer.appendChild(tag);
                modelInput.value = '';
            }
        }
    });

    // 取消按钮
    container.querySelector('#btn-cancel-add-provider').addEventListener('click', () => {
        addProviderFormVisible = false;
        renderConfigPage();
    });

    // 创建按钮
    container.querySelector('#btn-submit-add-provider').addEventListener('click', async () => {
        const id = container.querySelector('#new-provider-id').value.trim();
        const name = container.querySelector('#new-provider-name').value.trim();
        const baseUrl = container.querySelector('#new-provider-base-url').value.trim();
        const apiKey = container.querySelector('#new-provider-api-key').value.trim();
        const prefix = container.querySelector('#new-provider-prefix').value;

        if (!id || !name || !baseUrl) {
            alert('Provider ID、名称和 Base URL 为必填项');
            return;
        }

        try {
            const result = await api.createProvider({
                id, name, base_url: baseUrl,
                api_key: apiKey || undefined,
                litellm_prefix: prefix,
                models,
            });

            // 更新 state
            state.providers[id] = result.provider;
            addProviderFormVisible = false;
            selectedProviderId = id;
            renderConfigPage();
        } catch (error) {
            alert('创建失败: ' + error.message);
        }
    });
}

/**
 * 渲染通用设置
 */
function renderGeneralSettings(page) {
    const section = page.querySelector('.general-settings');
    if (!section) return;

    section.innerHTML = `
        <h3>对话参数</h3>
        <div class="detail-field">
            <label>Temperature</label>
            <div class="slider-row">
                <input type="range" id="cfg-temperature" min="0" max="2" step="0.1"
                       value="${state.config?.llm?.temperature || 0.7}">
                <span class="setting-value" id="cfg-temp-value">${state.config?.llm?.temperature || 0.7}</span>
            </div>
        </div>
        <div class="detail-field">
            <label>Max Tokens</label>
            <input type="number" id="cfg-max-tokens" value="${state.config?.llm?.max_tokens || 2000}"
                   min="100" max="8000">
        </div>

        <h3>音频 & 语音检测</h3>
        <div class="detail-field">
            <label>TTS 语音</label>
            <select id="cfg-tts-voice">
                <option value="zh-CN-XiaoxiaoNeural" ${state.config?.audio?.edge_tts_voice === 'zh-CN-XiaoxiaoNeural' ? 'selected' : ''}>晓晓（女声）</option>
                <option value="zh-CN-YunyangNeural" ${state.config?.audio?.edge_tts_voice === 'zh-CN-YunyangNeural' ? 'selected' : ''}>云扬（男声）</option>
                <option value="zh-CN-XiaoyiNeural" ${state.config?.audio?.edge_tts_voice === 'zh-CN-XiaoyiNeural' ? 'selected' : ''}>晓伊（女声）</option>
            </select>
        </div>
        <div class="detail-field">
            <label>自动检测语音结束</label>
            <input type="checkbox" id="cfg-vad-enabled" ${vadConfig.enabled ? 'checked' : ''}>
        </div>
        <div class="detail-field">
            <label>静音检测时长 (ms)</label>
            <div class="slider-row">
                <input type="range" id="cfg-vad-duration" min="500" max="3000" value="${vadConfig.silenceDuration}" step="100">
                <span class="setting-value" id="cfg-vad-duration-value">${vadConfig.silenceDuration}</span>
            </div>
        </div>

        <div class="form-actions" style="margin-top: 1.5rem;">
            <button class="btn-primary" id="btn-save-general">保存设置</button>
        </div>
    `;

    // Temperature slider
    const tempSlider = section.querySelector('#cfg-temperature');
    const tempValue = section.querySelector('#cfg-temp-value');
    if (tempSlider && tempValue) {
        tempSlider.addEventListener('input', () => {
            tempValue.textContent = tempSlider.value;
        });
    }

    // VAD duration slider
    const vadSlider = section.querySelector('#cfg-vad-duration');
    const vadValue = section.querySelector('#cfg-vad-duration-value');
    if (vadSlider && vadValue) {
        vadSlider.addEventListener('input', () => {
            vadValue.textContent = vadSlider.value;
        });
    }

    // Save button
    section.querySelector('#btn-save-general').addEventListener('click', async () => {
        try {
            const newConfig = {
                llm: {
                    temperature: parseFloat(tempSlider.value),
                    max_tokens: parseInt(section.querySelector('#cfg-max-tokens').value),
                },
                audio: {
                    edge_tts_voice: section.querySelector('#cfg-tts-voice').value,
                },
            };

            const data = await api.saveConfig(newConfig);
            if (data.success) {
                state.config = { ...state.config, ...newConfig };
                vadConfig.enabled = section.querySelector('#cfg-vad-enabled').checked;
                vadConfig.silenceDuration = parseInt(vadSlider.value) || 1500;
                alert('设置已保存');
            } else {
                alert('保存失败: ' + (data.error || '未知错误'));
            }
        } catch (error) {
            alert('保存失败: ' + error.message);
        }
    });
}

/**
 * 显示配置页面
 */
export function showConfigPage() {
    const page = document.getElementById('config-page');
    const app = document.querySelector('.app');
    if (page && app) {
        app.style.display = 'none';
        page.style.display = 'flex';
        selectedProviderId = state.activeProvider;
        addProviderFormVisible = false;
        renderConfigPage();
    }
}

/**
 * 隐藏配置页面
 */
export function hideConfigPage() {
    const page = document.getElementById('config-page');
    const app = document.querySelector('.app');
    if (page && app) {
        page.style.display = 'none';
        app.style.display = 'flex';
    }
}

/**
 * 初始化配置页面事件
 */
export function initConfigPage() {
    const page = document.getElementById('config-page');
    if (!page) return;

    // 返回按钮
    const backBtn = page.querySelector('#config-back-btn');
    if (backBtn) {
        backBtn.addEventListener('click', hideConfigPage);
    }

    // 添加 Provider 按钮
    const addBtn = page.querySelector('#btn-add-provider');
    if (addBtn) {
        addBtn.addEventListener('click', () => {
            addProviderFormVisible = !addProviderFormVisible;
            renderConfigPage();
        });
    }
}