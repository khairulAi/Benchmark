'use strict';
const byId = id => document.getElementById(id);
let currentId = null,
    events = null,
    poller = null,
    currentResult = null,
    uploadUrl = null;
const measuredRuns = new Map();
let deliveryRequests = 0,
    uploadSeconds = 0;

function el(tag, text, cls) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (cls) node.className = cls;
    return node;
}

function message(text) {
    byId('message').textContent = text;
    byId('message').style.display = 'block';
    clearTimeout(message.timer);
    message.timer = setTimeout(() => byId('message').style.display = 'none', 7000);
}
async function api(path, options = {}) {
    const response = await fetch(path, {
        ...options,
        cache: "no-store",
        signal: options.signal || AbortSignal.timeout(options.method && options.method !== "GET" ? 120000 : 15000)
    });
    if (!response.ok) {
        let detail;
        try {
            detail = (await response.json()).detail;
        } catch {
            detail = 'Request failed';
        }
        throw Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
    }
    return response.json();
}

function pct(value) {
    return value == null ? 'Not scored' : (value * 100).toFixed(1) + '%';
}
async function health() {
    try {
        const h = await api('/api/health');
        if (!health.initialized) {
            byId('stt-profile').value = h.default_stt_profile || 'zipformer';
            health.initialized = true;
        }
        const selected = h.stt_profiles?.[byId('stt-profile').value];
        const ready = Boolean(selected?.ready && h.speaker_models_ready);
        byId('health').textContent = `STT: ${selected?.model || h.stt_model} · CPU INT8 / ${h.cpu_threads} threads · Models ${ready ? 'ready' : 'need setup'} · LLM: ${h.llm_provider || 'not configured'} / ${h.llm_model || 'none'}`;
        byId('start').disabled = !ready || Boolean(h.active_run);
        for (const option of byId('stt-profile').options) {
            option.disabled = !h.stt_profiles?.[option.value]?.ready;
        }
    } catch {
        byId('health').textContent = 'Backend unavailable. Run START-BENCHMARK.cmd.';
        byId('start').disabled = true;
    }
}
async function listRuns() {
    try {
        const runs = await api('/api/runs');
        byId('runs').replaceChildren();
        for (const run of runs.filter(r => !r.test_fixture || new URLSearchParams(location.search).get('show_tests') === '1').slice(0, 25)) {
            const button = el('button', (run.test_fixture ? '[TEST] ' : '') + `${run.id.slice(0,8)} · ${run.status} · ${run.options.strategy} · ${run.options.noise_snr_db==null?'clean':run.options.noise_snr_db+' dB'}`);
            button.onclick = () => openRun(run.id);
            byId('runs').append(button);
        }
    } catch (e) {
        message(e.message);
    }
}

function stopWatch() {
    events?.close();
    events = null;
    clearInterval(poller);
    poller = null;
}

function progress(job) {
    byId('progress').textContent = `${job.id.slice(0,8)} · ${job.status}${job.processed_audio_seconds?' · '+job.processed_audio_seconds+' s audio processed':''}${job.diarization_progress!=null?' · '+Math.round(job.diarization_progress*100)+'% speakers':''}`;
}
async function openRun(id) {
    stopWatch();
    currentId = id;
    sessionStorage.setItem("meddesk-selected-run", id);
    deliveryRequests = 0;
    currentResult = null;
    byId('scores').textContent = '';
    try {
        await refreshResult(id);
        if (currentResult?.status === 'completed' || currentResult?.status === 'partial') {
            const ref = await api('/api/runs/' + id + '/reference');
            byId('reference').value = ref.transcript;
            byId('verified').checked = ref.verified;
            byId('verification-note').value = ref.verification_note || '';
            byId('timed-reference').value = ref.speaker_segments ? JSON.stringify(ref.speaker_segments, null, 2) : '';
            byId('expected-facts').value = ref.facts ? JSON.stringify(ref.facts, null, 2) : '';
        }
        const state = await api('/api/runs/' + id);
        if (!['completed', 'partial', 'failed', 'interrupted'].includes(state.job.status)) watch(id);
    } catch (e) {
        message(e.message);
    }
}
async function refreshResult(id) {
    const data = await api('/api/runs/' + id);
    if (id !== currentId) return;
    progress(data.job);
    if (data.result) {
        currentResult = data.result;
        render(data.result);
    }
    if (['completed', 'partial', 'failed', 'interrupted'].includes(data.job.status)) {
        stopWatch();
        byId('start').disabled = false;
        await listRuns();
    }
}

function beginPolling(id, interval = 2000) {
    clearInterval(poller);
    let inFlight = false,
        errorShown = false;
    poller = setInterval(async () => {
        if (id !== currentId || inFlight) return;
        inFlight = true;
        try {
            deliveryRequests++;
            await refreshResult(id);
            errorShown = false;
        } catch (e) {
            if (!errorShown) message('Status temporarily unavailable; retrying automatically. ' + e.message);
            errorShown = true;
        } finally {
            inFlight = false;
        }
    }, interval);
}

function watch(id) {
    if (byId('delivery').value !== 'sse') {
        beginPolling(id);
        return;
    }
    beginPolling(id, 5000);
    const connection = new EventSource(`/api/runs/${id}/events`);
    events = connection;
    deliveryRequests++;
    connection.onmessage = e => {
        if (id !== currentId || events !== connection) return;
        try {
            const job = JSON.parse(e.data);
            progress(job);
            if (['completed', 'partial', 'failed', 'interrupted'].includes(job.status)) refreshResult(id).catch(() => {});
        } catch {
            refreshResult(id).catch(() => {});
        }
    };
    connection.onerror = () => {
        if (id !== currentId || events !== connection) return;
        connection.close();
        events = null;
        beginPolling(id, 2000);
        message('Live progress disconnected; checking run status automatically. Processing is not restarted.');
    };
}

function render(result) {
    byId('empty').hidden = true;
    byId('result').hidden = false;
    byId('score').disabled = !['completed', 'partial'].includes(result.status);
    byId('extract-again').hidden = !['completed', 'partial'].includes(result.status);
    byId('download').hidden = false;
    byId('download').href = `/api/runs/${result.id}/download`;
    byId('download').textContent = 'Download run JSON ↓';
    byId('metrics').replaceChildren();
    const values = [
        ['Pipeline status', result.status],
        ['Total processing', result.timings.total_seconds == null ? 'Running…' : result.timings.total_seconds + ' s'],
        ['STT / LLM calls', `${result.calls?.stt_local_invocations??'…'} / ${result.calls?.llm_http_attempts??'…'}`],
        ['Provider cost', result.cost_usd == null ? 'Unknown' : '$' + result.cost_usd.toFixed(6)],
        ['WER', pct(result.metrics?.transcription?.wer?.rate)],
        ['Peak process RAM', result.peak_process_rss_mb ? result.peak_process_rss_mb + ' MB' : (result.timings.total_seconds == null ? 'Measuring…' : 'Not measured')]
    ];
    const noiseSignal = result.audio?.enhancement?.synthetic_reference_metrics;
    if (noiseSignal) values.push(['Synthetic SI-SDR', `${noiseSignal.before.si_sdr_db ?? 'unknown'} → ${noiseSignal.after.si_sdr_db ?? 'unknown'} dB`]);
    for (const [label, value] of values) {
        const card = el('div', undefined, 'metric');
        card.append(el('small', label), el('b', value));
        byId('metrics').append(card);
    }
    byId('warnings').replaceChildren();
    for (const warning of [...(result.warnings || []), ...(result.error ? [result.error] : []), ...(result.llm_error ? [result.llm_error] : [])]) byId('warnings').append(el('div', warning, 'warning'));
    if (noiseSignal && noiseSignal.after.si_sdr_db < noiseSignal.before.si_sdr_db) {
        byId('warnings').append(el('div', 'Enhancement reduced SI-SDR in this synthetic-reference test. Compare original/enhanced speech; improvement is not assumed.', 'warning'));
    }
    byId('transcript').replaceChildren();
    for (const u of result.transcript || []) {
        const row = el('div', undefined, 'utterance');
        if (u.voice_identity?.status === 'matched') row.append(el('b', `Voice match: ${u.voice_identity.name} · enrolled ${u.voice_identity.enrolled_role} · predicted`));
        row.append(el('small', `${u.id} · ${u.start.toFixed(1)}–${u.end.toFixed(1)}s · ${u.speaker} · ${u.role}`), el('div', u.text));
        const play = el('button', '▶ Listen to this utterance');
        play.onclick = () => {
            const player = byId('source-audio');
            player.src = '/api/runs/' + result.id + '/audio';
            player.onloadedmetadata = () => {
                player.currentTime = (result.audio?.clip_offset_seconds || 0) + u.start;
                player.play().catch(() => message('Playback unavailable for this source'));
            };
            player.ontimeupdate = () => {
                if (player.currentTime >= (result.audio?.clip_offset_seconds || 0) + u.end) player.pause();
            };
        };
        row.append(play);
        byId('transcript').append(row);
    }
    if (!result.transcript?.length) byId('transcript').append(el('p', 'Transcript will appear after STT and diarization complete.', 'muted'));
    byId('facts').replaceChildren();
    if (result.extraction) {
        byId('facts').append(el('p', result.extraction.summary_bn), el('p', 'Summary and facts are unverified model drafts.', 'muted'));
        for (const f of result.extraction.facts) {
            const row = el('div', undefined, 'fact');
            row.append(el('b', `${f.category} · ${f.polarity}: ${f.value}`), el('small', `${f.evidence_id} · “${f.quote}”`));
            byId('facts').append(row);
        }
    } else byId('facts').append(el('p', 'No structured output available.', 'muted'));
    byId('enhanced-player').hidden = !result.audio?.enhancement;
    byId('enhanced-audio').src = result.audio?.enhancement?.audio_url || '';
    byId('ledger').textContent = JSON.stringify({
        live_stream: result.live_stream,
        voice_matches: result.voice_matches,
        audio: result.audio,
        timings: result.timings,
        calls: result.calls,
        ledger: result.ledger,
        cost_note: result.cost_note,
        models: result.models,
        environment: result.environment,
        ui_delivery: {
            requests: deliveryRequests,
            upload_seconds: uploadSeconds,
            note: 'Session UI observations only; separate from provider calls.'
        }
    }, null, 2);
    if (result.metrics) byId('scores').textContent = JSON.stringify(result.metrics, null, 2);
    if (['completed', 'partial'].includes(result.status)) {
        if (result.execution_kind !== 'ui_test_fixture') measuredRuns.set(result.id, result);
        comparison();
    }
}

function comparison() {
    const table = el('table'),
        head = el('tr');
    for (const label of ['Run', 'Source', 'STT', 'Clip', 'Mode', 'SNR', 'Seconds', 'RTF', 'WER', 'CER', 'DER', 'Role', 'Fact F1', 'LLM calls', 'USD']) head.append(el('th', label));
    table.append(head);
    for (const r of measuredRuns.values()) {
        const row = el('tr');
        for (const value of [r.id.slice(0, 8), r.audio?.sha256?.slice(0, 8) || "unknown", r.models?.stt_id?.split("/").at(-1) || r.options.stt_profile, `${r.audio?.clip_offset_seconds}+${r.audio?.analyzed_seconds}s`, (r.execution_kind || r.options.strategy), r.options.noise_snr_db ?? 'clean', r.timings.total_seconds, r.timings.real_time_factor, pct(r.metrics?.transcription?.wer?.rate), pct(r.metrics?.transcription?.cer?.rate), pct(r.metrics?.der?.rate), pct(r.metrics?.role_accuracy?.rate), pct(r.metrics?.fact_f1?.f1), r.calls.llm_http_attempts, r.cost_usd ?? 'unknown']) row.append(el('td', String(value)));
        table.append(row);
    }
    byId('comparison').replaceChildren(table);
}
byId('start').onclick = async () => {
    if (byId('llm').checked && !byId('permission').checked) {
        message('Confirm transcript-sharing permission or disable LLM.');
        return;
    }
    const options = {
        denoise: byId('denoise').checked,
        identify_voices: byId('identify-voices').checked,
        stt_profile: byId('stt-profile').value,
        offset_seconds: Number(byId('offset').value),
        max_seconds: Number(byId('duration').value),
        num_speakers: Number(byId('speakers').value),
        strategy: byId('strategy').value,
        chunk_seconds: Number(byId('chunk').value),
        noise_snr_db: byId('noise').value === '' ? null : Number(byId('noise').value),
        use_llm: byId('llm').checked,
        remote_permission: byId('permission').checked
    };
    try {
        byId('start').disabled = true;
        let data;
        const tick = performance.now();
        if (byId('source').value === 'sample') data = await api('/api/runs/sample', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(options)
        });
        else {
            const file = byId('audio-file').files[0];
            if (!file) throw Error('Choose an audio file first');
            const form = new FormData();
            form.append('options', JSON.stringify(options));
            form.append('audio', file);
            data = await api('/api/runs/upload', {
                method: 'POST',
                body: form
            });
        }
        uploadSeconds = +(performance.now() - tick) / 1000;
        await openRun(data.id);
    } catch (e) {
        message(e.message);
        byId('start').disabled = false;
    }
};
byId('source').onchange = () => {
    byId('audio-file').hidden = byId('source').value !== 'upload';
    if (byId('source').value === 'sample') byId('source-audio').src = '/api/sample/audio';
};
byId('audio-file').onchange = () => {
    if (uploadUrl) URL.revokeObjectURL(uploadUrl);
    const file = byId('audio-file').files[0];
    if (file) {
        uploadUrl = URL.createObjectURL(file);
        byId('source-audio').src = uploadUrl;
    }
};
for (const button of document.querySelectorAll('[data-tab]')) button.onclick = () => {
    for (const tab of document.querySelectorAll('.tab')) tab.hidden = tab.id !== button.dataset.tab;
};
byId('load-script').onclick = async () => {
    try {
        const sample = await api('/api/sample');
        byId('reference').value = sample.script.map(u => u.text).join('\n');
        byId('verified').checked = false;
        message('Unverified full script loaded. Trim/correct it to match the exact analyzed clip before scoring.');
    } catch (e) {
        message(e.message);
    }
};
byId('score').onclick = async () => {
    if (!currentId) return;
    try {
        const reference = {
            transcript: byId('reference').value,
            verified: byId('verified').checked,
            verification_note: byId('verification-note').value,
            speaker_segments: byId('timed-reference').value.trim() ? JSON.parse(byId('timed-reference').value) : null,
            facts: byId('expected-facts').value.trim() ? JSON.parse(byId('expected-facts').value) : null
        };
        await api(`/api/runs/${currentId}/reference`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(reference)
        });
        await refreshResult(currentId);
        message('Reference saved. Scores require a verified reference.');
    } catch (e) {
        message(e.message);
    }
};
byId('export-comparison').onclick = () => {
    const table = byId('comparison').querySelector('table');
    if (!table) {
        message('Open completed runs first');
        return;
    }
    const csv = [...table.rows].map(row => [...row.cells].map(cell => '"' + cell.textContent.replaceAll('"', '""') + '"').join(',')).join('\r\n');
    const blob = new Blob(['\ufeff' + csv], {
            type: 'text/csv;charset=utf-8'
        }),
        url = URL.createObjectURL(blob),
        a = el('a');
    a.href = url;
    a.download = 'meddesk-comparison.csv';
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
};
byId('refresh').onclick = () => {
    health();
    listRuns();
    if (currentId) refreshResult(currentId).catch(e => message(e.message));
};
health();
listRuns();
api('/api/sample').then(sample => {
    byId('sample-name').textContent = sample.audio_name || 'No supplied conversation found';
}).catch(e => message(e.message));
byId('extract-again').onclick = async () => {
    if (!currentId || !byId('permission').checked) {
        message('Confirm transcript-sharing permission first.');
        return;
    }
    try {
        const next = await api('/api/runs/' + currentId + '/extract', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                remote_permission: true
            })
        });
        await openRun(next.id);
    } catch (e) {
        message(e.message);
    }
};
byId('stt-profile').onchange = health;
const rememberedRun = new URLSearchParams(location.search).get('run') || sessionStorage.getItem('meddesk-selected-run');
if (rememberedRun && /^[0-9a-f]{32}$/.test(rememberedRun)) openRun(rememberedRun);

function recoverVisibleRun() {
    if (currentId && document.visibilityState === 'visible') refreshResult(currentId).catch(() => {});
}
window.addEventListener('focus', recoverVisibleRun);
document.addEventListener('visibilitychange', recoverVisibleRun);
