/* PCM transport worklet. AudioContext requests 16 kHz; also handles a device
 * which chooses another rate. Continuous averaging retains phase across blocks. */
class MedDeskPCM extends AudioWorkletProcessor {
    constructor() {
        super();
        this.phase = 0;
        this.sum = 0;
        this.count = 0;
        this.buffer = new Int16Array(1600);
        this.used = 0;
        this.port.onmessage = event => {
            if (event.data === 'flush') {
                this.emit();
                this.port.postMessage({
                    type: 'flushed'
                });
            }
        };
    }
    emit() {
        if (!this.used) return;
        const data = this.buffer.slice(0, this.used);
        this.port.postMessage({
            type: 'pcm',
            buffer: data.buffer
        }, [data.buffer]);
        this.used = 0;
    }
    process(inputs) {
        const channels = inputs[0];
        if (!channels?.length) return true;
        for (let i = 0; i < channels[0].length; i++) {
            let value = 0;
            for (const channel of channels) value += channel[i] / channels.length;
            this.sum += value;
            this.count++;
            this.phase += 16000;
            if (this.phase >= sampleRate) {
                this.phase -= sampleRate;
                const sample = Math.max(-1, Math.min(1, this.sum / this.count));
                this.buffer[this.used++] = Math.round(sample * (sample < 0 ? 32768 : 32767));
                this.sum = 0;
                this.count = 0;
                if (this.used === this.buffer.length) this.emit();
            }
        }
        return true;
    }
}
registerProcessor('meddesk-pcm', MedDeskPCM);
