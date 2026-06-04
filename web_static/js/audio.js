/**
 * 音频处理模块（录音、播放、VAD）- AudioWorklet 流式版本
 *
 * 录音流程：
 *  1. AudioWorklet 输出 int16 PCM（100ms / chunk）
 *  2. 能量 VAD 检测语音开始 → 发 start_audio_stream
 *  3. 实时发 audio_chunk 给后端
 *  4. 后端 DashScope 检测句子结束 → 发回 vad_end → 前端停录
 *  5. 本地静音超时（1.2s）作为兜底
 */

import { state, logger, elements, vadConfig } from './state.js';
import * as ws from './ws.js';
import * as ui from './ui.js';

const SAMPLE_RATE = 16000;
const SILENCE_FALLBACK_MS = 1200; // 兜底：后端无响应时本地静音多久停录

// ─── 录音入口 ────────────────────────────────────────────────────────────────

export async function startRecording() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            audio: { sampleRate: SAMPLE_RATE, channelCount: 1, echoCancellation: true, noiseSuppression: true }
        });

        const audioContext = new AudioContext({ sampleRate: SAMPLE_RATE });
        await audioContext.audioWorklet.addModule('/static/worklets/pcm-processor.js');

        const source = audioContext.createMediaStreamSource(stream);
        const workletNode = new AudioWorkletNode(audioContext, 'pcm-processor');
        source.connect(workletNode);
        workletNode.connect(audioContext.destination); // 必须连出去 worklet 才运行

        // VAD 状态
        let isSpeechDetected = false;
        let speechStartTime = null;
        let streamStarted = false;        // 是否已发 start_audio_stream
        let silenceTimer = null;
        const recordingStartTime = Date.now();
        const MAX_DURATION = 30000;

        // 收到 PCM 块
        workletNode.port.onmessage = (e) => {
            if (!state.isRecording) return;

            const i16 = new Int16Array(e.data);
            const rms = computeRMS(i16);
            const now = Date.now();

            // 超时保护
            if (now - recordingStartTime > MAX_DURATION) {
                logger.info('[VAD] 录音超时，自动停止');
                stopRecording();
                return;
            }

            // ── 语音检测 ──
            if (rms > vadConfig.speechThreshold) {
                if (!isSpeechDetected) {
                    isSpeechDetected = true;
                    speechStartTime = now;
                    state.vad.isSpeaking = true;
                    state.vad.speechDetected = true;
                    updateRecordingIndicator('speaking');
                    logger.info('[VAD] 语音开始, rms=', rms.toFixed(4));

                    // 启动流式 ASR
                    if (!streamStarted) {
                        streamStarted = true;
                        ws.startAudioStream();
                    }
                }
                // 有语音 → 清除静音计时器
                if (silenceTimer) { clearTimeout(silenceTimer); silenceTimer = null; }

            } else if (isSpeechDetected) {
                // 语音后出现静音
                updateRecordingIndicator('silence');
                if (!silenceTimer) {
                    silenceTimer = setTimeout(() => {
                        if (!state.isRecording) return;
                        const dur = Date.now() - (speechStartTime || now);
                        if (dur >= vadConfig.minSpeechDuration) {
                            logger.info('[VAD] 静音超时（兜底），停止录音');
                            stopRecording();
                        } else {
                            isSpeechDetected = false;
                            state.vad.speechDetected = false;
                            state.vad.isSpeaking = false;
                            silenceTimer = null;
                            updateRecordingIndicator('listening');
                        }
                    }, SILENCE_FALLBACK_MS);
                }

            } else {
                // 未检测到语音
                if (now - recordingStartTime > 5000 && !isSpeechDetected) {
                    logger.info('[VAD] 5秒无语音，自动停止');
                    stopRecording();
                    return;
                }
            }

            // 发送 PCM 块（只在语音期间）
            if (streamStarted && state.isRecording) {
                ws.sendAudioChunk(i16.buffer);
            }
        };

        // 保存停录句柄
        state.mediaRecorder = {
            stop: () => {
                workletNode.disconnect();
                source.disconnect();
                stream.getTracks().forEach(t => t.stop());
                audioContext.close();
                if (silenceTimer) { clearTimeout(silenceTimer); silenceTimer = null; }
                if (streamStarted) ws.stopAudioStream();
            }
        };

        state.isRecording = true;
        elements.recordBtn.classList.add('recording');
        elements.recordingIndicator.classList.add('active');
        updateRecordingIndicator('listening');
        logger.info('[VAD] AudioWorklet 录音已启动');

    } catch (err) {
        logger.error('[VAD] 录音启动失败:', err);
        ui.showError('无法访问麦克风，请检查权限设置');
        throw err;
    }
}

// ─── 停录 ─────────────────────────────────────────────────────────────────────

export function stopRecording() {
    if (!state.isRecording || !state.mediaRecorder) return;

    logger.info('[VAD] 停止录音');
    state.mediaRecorder.stop();
    state.isRecording = false;
    state.vad.speechDetected = false;
    state.vad.isSpeaking = false;

    elements.recordBtn.classList.remove('recording');
    elements.recordingIndicator.classList.remove('active', 'vad-listening', 'vad-speaking', 'vad-silence');

    ui.showThinking('正在处理音频...');
}

// ─── 工具函数 ─────────────────────────────────────────────────────────────────

function computeRMS(i16) {
    let sum = 0;
    for (let i = 0; i < i16.length; i++) sum += (i16[i] / 32768) ** 2;
    return Math.sqrt(sum / i16.length);
}

function updateRecordingIndicator(status) {
    const el = elements.recordingIndicator;
    if (!el) return;
    el.classList.remove('vad-listening', 'vad-speaking', 'vad-silence');
    if (status === 'listening') el.classList.add('vad-listening');
    else if (status === 'speaking') el.classList.add('vad-speaking');
    else if (status === 'silence') el.classList.add('vad-silence');
}

// ─── 音频播放 ─────────────────────────────────────────────────────────────────

export function playAudio(base64Data) {
    elements.audioPlayer.src = `data:audio/mp3;base64,${base64Data}`;
    elements.audioPlayer.play().catch(e => logger.error('[VAD] 播放失败:', e));
}

let _streamingPlayer = null;

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
        if (!this.isPlaying) this._playNext();
    }

    _playNext() {
        if (this.chunks.has(this.nextChunkIndex)) {
            const data = this.chunks.get(this.nextChunkIndex);
            this.chunks.delete(this.nextChunkIndex++);
            this.audio.src = `data:audio/mp3;base64,${data}`;
            this.audio.play().catch(() => { this.isPlaying = false; });
            this.isPlaying = true;
        } else {
            this.isPlaying = false;
        }
    }

    finalize() { if (!this.isPlaying) this._playNext(); }

    reset() {
        this.chunks.clear();
        this.nextChunkIndex = 0;
        this.isPlaying = false;
        this.audio.pause();
        this.audio.src = '';
    }
}

export function playAudioChunk(base64Data, chunkIndex) {
    if (!_streamingPlayer) _streamingPlayer = new StreamingAudioPlayer();
    _streamingPlayer.addChunk(base64Data, chunkIndex);
}

export function finalizeAudioPlayback() {
    if (_streamingPlayer) _streamingPlayer.finalize();
}

export function resetStreamingPlayer() {
    if (_streamingPlayer) { _streamingPlayer.reset(); }
    _streamingPlayer = null;
}
