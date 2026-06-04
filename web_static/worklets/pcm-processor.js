/**
 * AudioWorklet 处理器：将 float32 音频转为 int16 PCM 块
 * 每 100ms（1600 samples @ 16kHz）输出一个块
 */
class PCMProcessor extends AudioWorkletProcessor {
    constructor() {
        super();
        this._buf = [];
        this._chunkSamples = 1600; // 100ms @ 16kHz
    }

    process(inputs) {
        const ch = inputs[0]?.[0];
        if (!ch) return true;

        for (let i = 0; i < ch.length; i++) this._buf.push(ch[i]);

        while (this._buf.length >= this._chunkSamples) {
            const f32 = this._buf.splice(0, this._chunkSamples);
            const i16 = new Int16Array(this._chunkSamples);
            for (let i = 0; i < this._chunkSamples; i++) {
                i16[i] = Math.max(-32768, Math.min(32767, f32[i] * 32768));
            }
            this.port.postMessage(i16.buffer, [i16.buffer]);
        }
        return true;
    }
}

registerProcessor('pcm-processor', PCMProcessor);
