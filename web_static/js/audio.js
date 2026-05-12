/**
 * 音频处理模块（录音、播放、VAD）- MediaRecorder 版本
 * 使用 MediaRecorder 录制音频，避免 ScriptProcessorNode 的缓冲区问题
 */

import { state, logger, elements, vadConfig } from './state.js';
import * as ws from './ws.js';
import * as ui from './ui.js';

// 录音配置
const SAMPLE_RATE = 16000;

/**
 * 开始录音 - 使用 MediaRecorder
 * @returns {Promise<void>}
 */
export async function startRecording() {
    try {
        // 获取麦克风权限
        const stream = await navigator.mediaDevices.getUserMedia({
            audio: {
                sampleRate: SAMPLE_RATE,
                channelCount: 1,
                echoCancellation: true,
                noiseSuppression: true
            }
        });

        // 创建音频上下文用于 VAD 分析
        const audioContext = new AudioContext({ sampleRate: SAMPLE_RATE });
        const source = audioContext.createMediaStreamSource(stream);
        const analyser = audioContext.createAnalyser();
        analyser.fftSize = 2048;
        analyser.smoothingTimeConstant = 0.8;
        source.connect(analyser);

        // 使用 MediaRecorder 录制音频
        const mediaRecorder = new MediaRecorder(stream, {
            mimeType: 'audio/webm;codecs=opus'
        });

        const audioChunks = [];
        let isSpeechDetected = false;
        let silenceTimer = null;
        let speechStartTime = null;

        // VAD 检测循环
        const vadInterval = setInterval(() => {
            const dataArray = new Uint8Array(analyser.frequencyBinCount);
            analyser.getByteFrequencyData(dataArray);

            // 计算音量（RMS）
            let sum = 0;
            for (let i = 0; i < dataArray.length; i++) {
                sum += dataArray[i] * dataArray[i];
            }
            const rms = Math.sqrt(sum / dataArray.length) / 255;

            const now = Date.now();

            if (rms > vadConfig.speechThreshold) {
                // 检测到语音
                if (!isSpeechDetected) {
                    isSpeechDetected = true;
                    state.vad.speechDetected = true;
                    state.vad.isSpeaking = true;
                    speechStartTime = now;
                    state.vad.speechStartTime = now;
                    updateRecordingIndicator('speaking');
                    logger.info('[WebUI] VAD: 检测到语音开始，rms=', rms.toFixed(4));
                }

                // 清除静音定时器
                if (silenceTimer) {
                    clearTimeout(silenceTimer);
                    silenceTimer = null;
                }
            } else if (isSpeechDetected) {
                // 语音中但音量低
                if (!silenceTimer) {
                    silenceTimer = setTimeout(() => {
                        const speechDuration = Date.now() - speechStartTime;
                        if (speechDuration >= vadConfig.minSpeechDuration) {
                            logger.info('[WebUI] VAD: 静音超时，自动停止录音');
                            stopRecording();
                        } else {
                            // 语音太短，重置状态
                            isSpeechDetected = false;
                            state.vad.speechDetected = false;
                            state.vad.isSpeaking = false;
                            silenceTimer = null;
                            updateRecordingIndicator('listening');
                            logger.info('[WebUI] VAD: 语音太短，继续等待');
                        }
                    }, vadConfig.silenceDuration);
                    updateRecordingIndicator('silence');
                }
            }
        }, 100);

        // MediaRecorder 数据可用回调
        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                audioChunks.push(event.data);
            }
        };

        // MediaRecorder 停止回调
        mediaRecorder.onstop = async () => {
            clearInterval(vadInterval);
            if (silenceTimer) clearTimeout(silenceTimer);

            // 合并所有音频块
            const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
            logger.info(`[WebUI] 录音完成: ${audioBlob.size} bytes, 语音检测=${isSpeechDetected}`);

            if (audioBlob.size === 0) {
                logger.warn('[WebUI] 没有录制到音频数据');
                ui.showError('未能识别语音，请重试');
                return;
            }

            // 转换为 ArrayBuffer 并发送
            try {
                const arrayBuffer = await audioBlob.arrayBuffer();
                const base64Audio = arrayBufferToBase64(arrayBuffer);

                logger.info('[WebUI] 音频 base64 长度:', base64Audio.length);

                // 发送音频数据（WebM 格式）
                ws.sendAudioData(base64Audio, 'audio/webm');
            } catch (error) {
                logger.error('[WebUI] 音频处理失败:', error);
                ui.showError('音频处理失败，请重试');
            }
        };

        // 开始录制
        mediaRecorder.start(100); // 每 100ms 收集一次数据

        // 保存引用
        state.mediaRecorder = {
            stop: () => {
                if (mediaRecorder.state !== 'inactive') {
                    mediaRecorder.stop();
                }
                stream.getTracks().forEach(track => track.stop());
                audioContext.close();
            }
        };

        state.isRecording = true;
        elements.recordBtn.classList.add('recording');
        elements.recordingIndicator.classList.add('active');
        updateRecordingIndicator('listening');

        logger.info('[WebUI] MediaRecorder 录音已启动');

    } catch (error) {
        logger.error('[WebUI] 录音失败:', error);
        ui.showError('无法访问麦克风，请检查权限设置');
        throw error;
    }
}

/**
 * 停止录音
 */
export function stopRecording() {
    if (!state.isRecording || !state.mediaRecorder) {
        return;
    }

    logger.info('[WebUI] 停止录音...');

    state.mediaRecorder.stop();
    state.isRecording = false;

    // 更新 UI
    elements.recordBtn.classList.remove('recording');
    elements.recordingIndicator.classList.remove('active');
    elements.recordingIndicator.classList.remove('vad-listening', 'vad-speaking', 'vad-silence');
}

/**
 * 将 ArrayBuffer 转换为 Base64 字符串
 * @param {ArrayBuffer} buffer - 二进制数据
 * @returns {string} Base64 字符串
 */
function arrayBufferToBase64(buffer) {
    const bytes = new Uint8Array(buffer);
    let binary = '';
    const chunkSize = 0x8000; // 32KB chunks

    for (let i = 0; i < bytes.length; i += chunkSize) {
        const chunk = bytes.subarray(i, i + chunkSize);
        binary += String.fromCharCode.apply(null, chunk);
    }

    return btoa(binary);
}

/**
 * 更新录音指示器状态
 * @param {string} status - 'listening' | 'speaking' | 'silence'
 */
function updateRecordingIndicator(status) {
    const indicator = elements.recordingIndicator;
    if (!indicator) return;

    indicator.classList.remove('vad-listening', 'vad-speaking', 'vad-silence');

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
 * 播放音频
 * @param {string} base64Data - Base64 编码的音频数据
 */
export function playAudio(base64Data) {
    const audioSrc = `data:audio/mp3;base64,${base64Data}`;
    elements.audioPlayer.src = audioSrc;
    elements.audioPlayer.play().catch(error => {
        logger.error('[WebUI] 播放音频失败:', error);
    });
}

// 流式音频播放器状态
let _streamingPlayer = null;

/**
 * 流式音频播放器类
 * 管理音频块的缓冲和连续播放
 */
class StreamingAudioPlayer {
    constructor() {
        this.chunks = new Map();
        this.nextChunkIndex = 0;
        this.isPlaying = false;
        this.audio = new Audio();
        this.audio.addEventListener('ended', () => this._playNext());
    }

    addChunk(base64Data, index) {
        this.chunks.set(index, base64Data);
        if (!this.isPlaying) {
            this._playNext();
        }
    }

    _playNext() {
        if (this.chunks.has(this.nextChunkIndex)) {
            const base64Data = this.chunks.get(this.nextChunkIndex);
            this.chunks.delete(this.nextChunkIndex);
            this.nextChunkIndex++;

            this.audio.src = `audio/mp3;base64,${base64Data}`;
            this.audio.play().catch(error => {
                logger.error('[WebUI] 播放音频块失败:', error);
                this.isPlaying = false;
            });
            this.isPlaying = true;
        } else {
            this.isPlaying = false;
        }
    }

    finalize() {
        if (!this.isPlaying) {
            this._playNext();
        }
    }

    reset() {
        this.chunks.clear();
        this.nextChunkIndex = 0;
        this.isPlaying = false;
        this.audio.pause();
        this.audio.src = '';
    }
}

/**
 * 播放音频块（流式TTS）
 * @param {string} base64Data - Base64 编码的音频数据
 * @param {number} chunkIndex - 块索引
 */
export function playAudioChunk(base64Data, chunkIndex) {
    if (!_streamingPlayer) {
        _streamingPlayer = new StreamingAudioPlayer();
    }
    _streamingPlayer.addChunk(base64Data, chunkIndex);
}

/**
 * 完成流式音频播放
 */
export function finalizeAudioPlayback() {
    if (_streamingPlayer) {
        _streamingPlayer.finalize();
    }
}

/**
 * 重置流式音频播放器
 */
export function resetStreamingPlayer() {
    if (_streamingPlayer) {
        _streamingPlayer.reset();
    }
    _streamingPlayer = null;
}
