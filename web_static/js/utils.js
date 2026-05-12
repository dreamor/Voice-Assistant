/**
 * 工具函数模块
 */

/**
 * HTML 转义，防止 XSS
 * @param {string} text - 原始文本
 * @returns {string} 转义后的 HTML
 */
export function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Blob 转 Base64
 * @param {Blob} blob - 二进制数据
 * @returns {Promise<string>} Base64 字符串
 */
export function blobToBase64(blob) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onloadend = () => {
            try {
                const base64 = reader.result.split(',')[1];
                // 验证 base64 长度是否合理
                if (!base64 || base64.length < 100) {
                    reject(new Error('Invalid base64 data'));
                    return;
                }
                resolve(base64);
            } catch (e) {
                reject(e);
            }
        };
        reader.onerror = reject;
        reader.readAsDataURL(blob);
    });
}

/**
 * Blob 转 Base64 (使用 ArrayBuffer)
 * @param {Blob} blob - 二进制数据
 * @returns {Promise<string>} Base64 字符串
 */
export function blobToBase64Buffer(blob) {
    return new Promise((resolve, reject) => {
        blob.arrayBuffer()
            .then(buffer => {
                const bytes = new Uint8Array(buffer);
                // 使用更可靠的 base64 编码方法
                const base64 = arrayBufferToBase64(bytes);
                resolve(base64);
            })
            .catch(reject);
    });
}

/**
 * Uint8Array 转 Base64
 * @param {Uint8Array} bytes - 字节数组
 * @returns {string} Base64 字符串
 */
function arrayBufferToBase64(bytes) {
    const CHUNK_SIZE = 0x8000; // 32k chunks
    let result = '';
    for (let i = 0; i < bytes.length; i += CHUNK_SIZE) {
        const chunk = bytes.subarray(i, i + CHUNK_SIZE);
        result += String.fromCharCode.apply(null, chunk);
    }
    return btoa(result);
}

/**
 * 格式化消息内容（支持 Markdown 子集）
 * @param {string} content - 原始内容
 * @returns {string} HTML 内容
 */
export function formatMessageContent(content) {
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

/**
 * 自动调整 textarea 高度
 * @param {HTMLTextAreaElement} textarea - 输入框元素
 * @param {number} maxHeight - 最大高度（默认 200）
 */
export function autoResizeTextarea(textarea, maxHeight = 200) {
    textarea.addEventListener('input', () => {
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, maxHeight) + 'px';
    });
}
