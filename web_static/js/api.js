/**
 * API 请求模块
 */

import { state, logger } from './state.js';

/**
 * 加载配置
 * @returns {Promise<Object>}
 */
export async function loadConfig() {
    try {
        const response = await fetch('/api/config');
        state.config = await response.json();
        return state.config;
    } catch (error) {
        logger.error('[WebUI] 加载配置失败:', error);
        throw error;
    }
}

/**
 * 加载模型列表
 * @returns {Promise<string[]>}
 */
export async function loadModels() {
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
        return state.models;
    } catch (error) {
        logger.error('[WebUI] 加载模型列表失败:', error);
        state.models = [state.config.llm?.model || 'qwen-turbo'];
        state.modelsInfo = { total: 0, language: 0, checked: false };
        throw error;
    }
}

/**
 * 加载历史记录
 * @returns {Promise<Array>}
 */
export async function loadHistory() {
    try {
        const response = await fetch('/api/history');
        const data = await response.json();
        return data.conversations || [];
    } catch (error) {
        logger.error('[WebUI] 加载历史记录失败:', error);
        return [];
    }
}

/**
 * 加载指定对话
 * @param {string} id - 对话 ID
 * @returns {Promise<Object>}
 */
export async function loadConversation(id) {
    try {
        const response = await fetch(`/api/history/${id}`);
        const data = await response.json();
        if (data.error) {
            throw new Error(data.error);
        }
        return data;
    } catch (error) {
        logger.error('[WebUI] 加载对话失败:', error);
        throw error;
    }
}

/**
 * 删除对话
 * @param {string} id - 对话 ID
 * @returns {Promise<Object>}
 */
export async function deleteConversation(id) {
    try {
        const response = await fetch(`/api/history/${id}`, { method: 'DELETE' });
        return await response.json();
    } catch (error) {
        logger.error('[WebUI] 删除对话失败:', error);
        throw error;
    }
}

/**
 * 批量删除对话
 * @param {string[]} ids - 对话 ID 列表
 * @returns {Promise<{deleted: number}>}
 */
export async function batchDeleteConversations(ids) {
    try {
        const response = await fetch('/api/history/batch-delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ids })
        });
        return await response.json();
    } catch (error) {
        logger.error('[WebUI] 批量删除对话失败:', error);
        throw error;
    }
}

/**
 * 保存配置
 * @param {Object} config - 新配置
 * @returns {Promise<Object>}
 */
export async function saveConfig(config) {
    try {
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || '服务器错误');
        }
        return await response.json();
    } catch (error) {
        logger.error('[WebUI] 保存配置失败:', error);
        throw error;
    }
}

/**
 * 切换模型
 * @param {string} model - 模型名称
 * @returns {Promise<Object>}
 */
export async function switchModel(model) {
    try {
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ llm: { model: model } })
        });
        return await response.json();
    } catch (error) {
        logger.error('[WebUI] 切换模型失败:', error);
        throw error;
    }
}

/**
 * 加载 Provider 列表
 * @returns {Promise<Object>}
 */
export async function loadProviders() {
    try {
        const response = await fetch('/api/providers');
        const data = await response.json();
        return data;
    } catch (error) {
        logger.error('[WebUI] 加载 Provider 列表失败:', error);
        throw error;
    }
}

/**
 * 切换 Provider
 * @param {string} providerId - Provider ID
 * @param {string} [modelId] - 可选的模型 ID
 * @returns {Promise<Object>}
 */
export async function switchProvider(providerId, modelId) {
    try {
        const response = await fetch('/api/providers/switch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ provider_id: providerId, model_id: modelId || undefined })
        });
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || '切换失败');
        }
        return await response.json();
    } catch (error) {
        logger.error('[WebUI] 切换 Provider 失败:', error);
        throw error;
    }
}

/**
 * 设置 Provider API Key
 * @param {string} providerId - Provider ID
 * @param {string} apiKey - API Key
 * @returns {Promise<Object>}
 */
export async function setProviderApiKey(providerId, apiKey) {
    try {
        const response = await fetch('/api/providers/api-key', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ provider_id: providerId, api_key: apiKey })
        });
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || '设置失败');
        }
        return await response.json();
    } catch (error) {
        logger.error('[WebUI] 设置 API Key 失败:', error);
        throw error;
    }
}

/**
 * 创建自定义 Provider
 * @param {Object} data - Provider 配置
 * @returns {Promise<Object>}
 */
export async function createProvider(data) {
    try {
        const response = await fetch('/api/providers/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || '创建失败');
        }
        return await response.json();
    } catch (error) {
        logger.error('[WebUI] 创建 Provider 失败:', error);
        throw error;
    }
}

/**
 * 删除自定义 Provider
 * @param {string} providerId - Provider ID
 * @returns {Promise<Object>}
 */
export async function deleteProvider(providerId) {
    try {
        const response = await fetch(`/api/providers/${providerId}`, {
            method: 'DELETE'
        });
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || '删除失败');
        }
        return await response.json();
    } catch (error) {
        logger.error('[WebUI] 删除 Provider 失败:', error);
        throw error;
    }
}

/**
 * 部分更新自定义 Provider
 * @param {string} providerId - Provider ID
 * @param {Object} patch - 可选字段 base_url / name / models / litellm_prefix
 * @returns {Promise<Object>}
 */
export async function updateProvider(providerId, patch) {
    try {
        const response = await fetch(`/api/providers/${providerId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(patch)
        });
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || '更新失败');
        }
        return await response.json();
    } catch (error) {
        logger.error('[WebUI] 更新 Provider 失败:', error);
        throw error;
    }
}

/**
 * 从 Provider 获取模型列表
 * @param {string} providerId - Provider ID
 * @returns {Promise<Object>}
 */
export async function fetchProviderModels(providerId) {
    try {
        const response = await fetch(`/api/providers/${providerId}/models`);
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || '获取失败');
        }
        return await response.json();
    } catch (error) {
        logger.error('[WebUI] 获取 Provider 模型列表失败:', error);
        throw error;
    }
}
