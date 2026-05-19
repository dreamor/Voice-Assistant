/**
 * Voice Assistant - MCP / Skill 管理面板
 * 嵌入到配置页底部的两个 section：MCP servers (只读) 和 Skills（启停 / 重载）
 */

import * as api from './api.js';
import { logger } from './state.js';

/**
 * 渲染整个 MCP/Skill 区块
 */
export async function renderMcpSkillSections() {
    await Promise.all([renderMcpSection(), renderSkillSection()]);
}

async function renderMcpSection() {
    const container = document.querySelector('.mcp-server-list');
    if (!container) return;

    container.innerHTML = '<div class="detail-empty">加载中...</div>';
    try {
        const data = await api.fetchMcpServers();
        const servers = data.servers || [];
        if (servers.length === 0) {
            container.innerHTML = '<div class="detail-empty">暂无 MCP server（编辑 config/mcp_servers.yaml 后重启生效）</div>';
            return;
        }
        container.innerHTML = servers.map(renderMcpServerRow).join('');
    } catch (error) {
        logger.error('[MCP] 加载失败', error);
        container.innerHTML = `<div class="detail-empty">加载失败: ${escapeHtml(error.message || '未知错误')}</div>`;
    }
}

/**
 * @param {{id:string,transport:string,enabled:boolean,ready:boolean,error:?string,tools:string[]}} server
 */
function renderMcpServerRow(server) {
    const statusIcon = server.ready ? '✓' : '✗';
    const statusClass = server.ready ? 'mcp-ok' : 'mcp-fail';
    const errorHtml = server.error
        ? `<div class="mcp-error">error: ${escapeHtml(server.error)}</div>`
        : '';
    const toolsHtml = server.tools && server.tools.length
        ? `<div class="mcp-tools">tools: ${server.tools.map(escapeHtml).join(', ')}</div>`
        : '<div class="mcp-tools mcp-tools-empty">tools: (无)</div>';
    return `
        <div class="mcp-row">
            <div class="mcp-row-header">
                <span class="${statusClass}">${statusIcon}</span>
                <strong>${escapeHtml(server.id)}</strong>
                <span class="mcp-transport">[${escapeHtml(server.transport)}]</span>
                ${server.enabled ? '' : '<span class="mcp-disabled">(disabled)</span>'}
            </div>
            ${errorHtml}
            ${toolsHtml}
        </div>
    `;
}

async function renderSkillSection() {
    const container = document.querySelector('.skill-list');
    if (!container) return;

    container.innerHTML = '<div class="detail-empty">加载中...</div>';
    try {
        const data = await api.fetchSkills();
        const skills = data.skills || [];
        if (skills.length === 0) {
            container.innerHTML = '<div class="detail-empty">暂无 skill（在 skills/ 目录放置 SKILL.md 后点击重载）</div>';
            return;
        }
        container.innerHTML = skills.map(renderSkillRow).join('');
        wireSkillToggles();
    } catch (error) {
        logger.error('[Skill] 加载失败', error);
        container.innerHTML = `<div class="detail-empty">加载失败: ${escapeHtml(error.message || '未知错误')}</div>`;
    }
}

/**
 * @param {{name:string,description:string,trigger:string,keywords:string[],enabled:boolean,deps_ok:boolean,deps_missing:?Object}} skill
 */
function renderSkillRow(skill) {
    const keywords = skill.keywords && skill.keywords.length
        ? skill.keywords.map(k => `<code>${escapeHtml(k)}</code>`).join(', ')
        : '(none)';
    const depsHtml = skill.deps_ok
        ? '<span class="skill-deps-ok">依赖完整</span>'
        : renderMissingDeps(skill.deps_missing);
    return `
        <div class="skill-row" data-skill="${escapeHtml(skill.name)}">
            <div class="skill-row-header">
                <label class="skill-toggle">
                    <input type="checkbox" class="skill-enabled-input" ${skill.enabled ? 'checked' : ''}>
                    <span>${escapeHtml(skill.name)}</span>
                </label>
                <span class="skill-trigger">[${escapeHtml(skill.trigger)}]</span>
            </div>
            <div class="skill-description">${escapeHtml(skill.description || '')}</div>
            <div class="skill-meta">关键词: ${keywords}</div>
            <div class="skill-meta">${depsHtml}</div>
        </div>
    `;
}

function renderMissingDeps(missing) {
    if (!missing) return '';
    const parts = [];
    if (missing.mcp_servers?.length) {
        parts.push(`缺 MCP: ${missing.mcp_servers.map(escapeHtml).join(', ')}`);
    }
    if (missing.python?.length) {
        parts.push(`缺 Python: ${missing.python.map(escapeHtml).join(', ')}`);
    }
    if (missing.brew?.length) {
        parts.push(`缺 brew: ${missing.brew.map(escapeHtml).join(', ')}`);
    }
    if (missing.env?.length) {
        parts.push(`缺 env: ${missing.env.map(escapeHtml).join(', ')}`);
    }
    return `<span class="skill-deps-missing">${parts.join(' · ')}</span>`;
}

function wireSkillToggles() {
    document.querySelectorAll('.skill-row').forEach((row) => {
        const input = row.querySelector('.skill-enabled-input');
        if (!input) return;
        input.addEventListener('change', async () => {
            const name = row.getAttribute('data-skill');
            if (!name) return;
            input.disabled = true;
            try {
                await api.toggleSkill(name, input.checked);
            } catch (error) {
                logger.error('[Skill] 切换失败', error);
                input.checked = !input.checked;
                alert(`切换失败: ${error.message || error}`);
            } finally {
                input.disabled = false;
            }
        });
    });
}

/**
 * 给配置页绑定 reload / refresh 按钮
 */
export function initMcpSkillUi() {
    const reloadBtn = document.getElementById('btn-reload-skills');
    if (reloadBtn) {
        reloadBtn.addEventListener('click', async () => {
            reloadBtn.disabled = true;
            try {
                await api.reloadSkills();
                await renderSkillSection();
            } catch (error) {
                logger.error('[Skill] 重载失败', error);
                alert(`重载失败: ${error.message || error}`);
            } finally {
                reloadBtn.disabled = false;
            }
        });
    }
    const refreshBtn = document.getElementById('btn-refresh-mcp');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', renderMcpSection);
    }
}

function escapeHtml(s) {
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}
