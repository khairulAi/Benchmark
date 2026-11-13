/* Live capture and local biometric enrollment, separate from batch rendering. */
'use strict';
(() => {
    let live = null;
    let ready = false;

    async function loadProfiles() {
        const list = byId('voice-profiles');
        try {
            const data = await api('/api/voices');
            list.replaceChildren();
            if (!data.profiles.length) list.append(el('p', 'No voice signatures enrolled.', 'muted'));
            for (const profile of data.profiles) {
                const row = el('div', undefined, 'voice-profile');
                row.append(el('span', `${profile.name} · ${profile.role}`));
                const remove = el('button', 'Delete signature');
                remove.type = 'button';
                remove.onclick = async () => {
                    try {
                        await api('/api/voices/' + profile.id, {
                            method: 'DELETE'
                        });
                        await loadProfiles();
                    } catch (error) {
                        message(error.message);
                    }
                };
                row.append(remove);
                list.append(row);
            }
        } catch (error) {
            list.textContent = error.message;
        }
    }

    byId('voice-form').onsubmit = async event => {
        event.preventDefault();
        const file = byId('voice-file').files[0];
        if (!file || !byId('voice-consent').checked) return;
        const body = new FormData();
        body.append('name', byId('voice-name').value);
        body.append('role', byId('voice-role').value);
        body.append('consent', 'true');
        body.append('audio', file);
        byId('voice-enroll').disabled = true;
        try {
            await api('/api/voices', {
                method: 'POST',
                body
            });
            byId('voice-form').reset();
            message('Encrypted voice signature saved. Enrollment recording deleted.');
            await loadProfiles();
        } catch (error) {
            message(error.message);
        } finally {
            byId('voice-enroll').disabled = false;
        }
    };

    async function releaseMicrophone(state) {
        if (state.node) state.node.disconnect();
        if (state.source) state.source.disconnect();
        if (state.stream)
            for (const track of state.stream.getTracks()) track.stop();
        if (state.context && state.context.state !== 'closed') await state.context.close();
    }

    async function abort(state, detail) {
        if (live !== state) return;
        live = null;
        clearTimeout(state.stopTimer);
        await releaseMicrophone(state);
        if (state.socket?.readyState < 2) state.socket.close();
        byId('live-status').textContent = detail;
        byId('live-start').disabled = !ready;
        byId('live-stop').disabled = true;
        health();
    }

    byId('live-start').onclick = async () => {
        if (live) return;
        if (!byId('live-consent').checked) {
            message('Confirm recording permission first.');
            return;
        }
        if (byId('llm').checked && !byId('permission').checked) {
            message('Confirm transcript sharing or disable LLM.');
            return;
        }
        const state = {
            sent: 0,
            ack: 0,
            stopping: false,
            recording: false
        };
        live = state;
        byId('live-start').disabled = true;
        byId('live-status').textContent = 'Opening microphone and loading streaming model…';
        byId('live-text').value = '';
        try {
            state.stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    channelCount: 1,
                    echoCancellation: true
                },
                video: false
            });
            state.context = new AudioContext({
                sampleRate: 16000
            });
            await state.context.resume();
            await state.context.audioWorklet.addModule('/live-worklet.js');
            state.source = state.context.createMediaStreamSource(state.stream);
            state.node = new AudioWorkletNode(state.context, 'meddesk-pcm');
            state.node.port.onmessage = event => {
                if (live !== state) return;
                if (event.data.type === 'pcm' && state.recording) {
                    if (state.sent - state.ack > 30 || state.socket.bufferedAmount > 256000) {
                        abort(state, 'CPU/network cannot keep up. Session stopped without silently dropping audio.');
                        return;
                    }
                    state.socket.send(event.data.buffer);
                    state.sent++;
                }
                if (event.data.type === 'flushed' && state.stopping) {
                    state.recording = false;
                    state.socket.send(JSON.stringify({
                        type: 'stop'
                    }));
                    releaseMicrophone(state);
                }
            };
            state.source.connect(state.node);
            // Worklet output is silent; connecting keeps it processing without feedback.
            state.node.connect(state.context.destination);
            const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
            state.socket = new WebSocket(`${protocol}//${location.host}/api/live`);
            state.socket.onopen = () => state.socket.send(JSON.stringify({
                type: 'start',
                sample_rate: 16000,
                consent: true,
                options: {
                    stt_profile: byId('stt-profile').value,
                    max_seconds: 0,
                    offset_seconds: 0,
                    num_speakers: Number(byId('speakers').value),
                    use_llm: byId('llm').checked,
                    remote_permission: byId('permission').checked,
                    denoise: byId('denoise').checked,
                    identify_voices: byId('identify-voices').checked
                }
            }));
            state.socket.onmessage = async event => {
                const data = JSON.parse(event.data);
                if (data.type === 'ready') {
                    state.recording = true;
                    byId('live-stop').disabled = false;
                    byId('live-status').textContent = 'Recording · live Bengali draft';
                } else if (data.type === 'partial') {
                    state.ack = data.ack;
                    byId('live-text').value = data.text;
                    byId('live-status').textContent = `Recording · ${data.audio_seconds.toFixed(1)} s · live draft`;
                } else if (data.type === 'final') {
                    clearTimeout(state.stopTimer);
                    byId('live-text').value = data.text;
                    byId('live-status').textContent = 'Live capture saved. Final analysis running…';
                    live = null;
                    await releaseMicrophone(state);
                    byId('live-start').disabled = false;
                    await openRun(data.final_run.id);
                } else if (data.type === 'error') {
                    await abort(state, data.detail);
                }
            };
            state.socket.onerror = () => abort(state, 'Live connection failed; check the backend.');
            state.socket.onclose = () => {
                if (live === state) abort(state, 'Live connection closed. Incomplete capture was discarded.');
            };
        } catch (error) {
            await abort(state, error.message);
        }
    };

    byId('live-stop').onclick = () => {
        if (!live || live.stopping) return;
        live.stopping = true;
        byId('live-stop').disabled = true;
        byId('live-status').textContent = 'Finishing capture and queuing final analysis…';
        live.node.port.postMessage('flush');
        const state = live;
        state.stopTimer = setTimeout(() => abort(state, 'Finalization timed out; connection closed.'), 30000);
    };
    window.addEventListener('pagehide', () => {
        if (live) {
            releaseMicrophone(live);
            live.socket?.close();
        }
    });
    api('/api/health').then(data => {
        ready = data.streaming_ready;
        byId('live-start').disabled = !ready;
        byId('live-status').textContent = ready ? 'Ready for Bengali live capture.' : 'Streaming model missing; run SETUP-BACKEND.cmd.';
        byId('denoise').disabled = !data.denoiser_ready;
    }).catch(() => {
        byId('live-start').disabled = true;
    });
    loadProfiles();
})();
