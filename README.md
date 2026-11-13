# MedDesk Bengali Speech Benchmark — v2.1

A local research workspace for Bengali doctor–patient conversations: audio collection, CPU speech recognition, speaker diarization, role attribution, evidence-backed structured extraction and reproducible evaluation.

বাংলা নির্দেশনা: [USER-GUIDE-BN.md](USER-GUIDE-BN.md).

## Start here

1. Keep your provider key in `.env` (`LLM_API_KEY`). Never commit it.
2. On this configured computer, run **START-BENCHMARK.cmd** (START-MEDDESK.cmd also forwards to it).
3. The launcher reuses the workspace server or chooses a free port from 8787-8792. It does not stop other apps.
4. Open the address printed by the launcher in Chrome (normally **http://localhost:8787/benchmark.html**).
5. Choose the supplied conversation or upload audio. Start with a 120-second clip.
6. Confirm permission before sending transcript to the configured provider, or disable LLM for local-only processing.
7. Run, review the speaker-attributed transcript and cited facts, then download the run JSON.

The original recording interface remains at http://localhost:8787/. Its data stays in browser IndexedDB; benchmark runs are stored by the backend in `data/runs/`. These are separate stores. See RECORDING-STUDIO.md for the collection interface.

## Installation on another Windows machine

Use Python and run **SETUP-BACKEND.cmd**. It installs project-local Python 3.11, dependencies and the small Bengali Zipformer INT8 model plus speaker weights. Several GB of disk space and internet access are needed for initial setup. No GPU is required. An existing Python installation is needed to bootstrap uv. Downloads and installation can take time.

For this machine, C: had insufficient disk space. Model weights and conversion tools are located under **E:/MedDesk-model-cache/**. `.env` contains `MODELS_DIR` for that location. Do not remove that folder while using the backend. The production environment is `.venv` in this project. The default is Bengali Zipformer INT8. IndicConformer, BanglaASR and Vivasoft are alternative profiles; only installed profiles can be selected. STT and speaker models are loaded sequentially to limit memory. CPU speed and memory vary by audio length and machine.

For a fresh machine, copy `.env.example` to `.env`, enter a key and optionally configure a model directory on a drive with space. The example is safe to share; `.env` is not. The setup script uses the project drive for package cache by default, so choose a project drive with sufficient space. The original conversation and reference recordings are excluded from Git; supply them separately with appropriate permission or upload new audio.

## Models and execution

| Component | Implementation |
| --- | --- |
| Default Bengali STT | SayedShaun/bangla-zipformer-onnx INT8, sherpa-onnx CPU, ≤15-second acoustic chunks |
| Alternative STT | OpenVoiceOS Bengali IndicConformer INT8; existing BanglaASR/Vivasoft Whisper INT8 |
| Speaker segmentation | Public sherpa-onnx conversion of pyannote segmentation 3.0 |
| Speaker embeddings/clustering | 3D-Speaker ERes2Net + sherpa-onnx clustering |
| Role detection and extraction | Model configured by LLM_MODEL through LLM_BASE_URL; currently mistralai/mistral-large-2512 through Xkiro |
| Server | FastAPI / Uvicorn, bound to loopback |
| UI | HTML, CSS, plain JavaScript |

Speaker clusters identify **which voice spoke when within one recording**, not a real person's name. Speaker labels may change between runs. Doctor/patient roles are inferred from the transcript and can be unknown. The embedding model was not specifically validated on Bengali clinical speech; evaluate it on your target recordings. Optional local voice enrollment now maps clusters to encrypted profiles. A similarity match is a prediction; unfamiliar or ambiguous voices remain unknown. This is not the pyannote community-1 pipeline.

The reading script and human reference are never included in the LLM input. The provider receives only the generated speaker-attributed transcript and output schema. Audio processing remains local. The provider's privacy/retention policies apply to the transcript sent to it.

Model weights are public downloads, with source URLs, the STT revision and SHA-256 hashes recorded in `models/manifest.json` (or MODELS_DIR). Review upstream model licenses for your intended deployment; the application does not grant additional rights to weights or recordings.

## What happens in a run

1. Decode and downmix to mono 16 kHz, select the requested clip.
2. Optionally add deterministic synthetic white noise at a specified SNR (seed 42).
3. Run Bengali transcription with word timestamps and VAD.
4. Release STT model; load speaker diarization models and cluster voices.
5. Match words to speaker segments by overlap. Ambiguous overlap/unmatched words are marked unknown.
6. Optionally send the generated utterances to the configured LLM once for role attribution and structured facts.
7. Validate JSON, speaker references and exact evidence quotes. Unsupported evidence is discarded with warnings. Semantic correctness still requires human review.
8. Save timings, invocation ledger, environment/model versions, outputs and warnings.

A failed LLM call does not erase successful STT/diarization outputs: the run is marked partial. There are no hidden automatic retries or repair calls. Use Re-run extraction for an explicit new audited run that reuses STT/diarization; the parent run is preserved. Extraction-only latency is not full-pipeline latency. Interruptions survive as run records but are not resumed automatically. One CPU run is processed at a time; concurrent requests return HTTP 409. Refreshing or disconnecting the browser does not cancel an active run.

## Experiments and transport

- **Single file:** one local transcribe invocation; the decoder can internally use multiple windows.
- **Independent chunks:** multiple local transcribe invocations using the selected chunk size. Boundaries can lose words/context; overlap stitching is not implemented.
- **Original/noise:** compare the same clip with original audio and synthetic 20/10/0 dB noise.
- **SSE/polling:** choose server-pushed job status or a two-second polling interval. This compares status delivery, not streaming speech recognition.

**Live microphone:** the separate Live conversation panel sends PCM over a real WebSocket to a stateful Bengali streaming model. Stop saves the capture locally and starts the selected final STT, speaker, optional enhancement/identity and Mistral stages. Live decoder steps and final model calls are measured separately. Speaker clustering/roles are finalized after stop; continuous online speaker labeling is not claimed. Browser-based multi-model sweeps remain outside the interface; use the comparison script.

## Ground truth and scoring

The provided DOCX is an **unverified reading script**. It must be checked against what was actually said. For a short clip, trim the reference to that exact clip; never compare a full script against a partial recording.

1. Listen to the exact clip and enter/correct its actual transcript.
2. Tick the human verification checkbox and add a reviewer note.
3. Save reference and evaluate.
4. Optionally provide timed speaker reference segments and expected facts as JSON in the expandable controls.

No verified reference means **no accuracy claim**. No timed speaker reference means DER and role accuracy remain unavailable. No expected fact list means fact F1 is unavailable. Empty expected facts (`[]`) explicitly means no facts were expected, not missing annotation.

Example timed reference, relative to clip start:

```json
[{"start": 0, "end": 2.5, "speaker": "A", "role": "patient"},
 {"start": 2.5, "end": 6, "speaker": "B", "role": "doctor"}]
```

Example expected fact:

```json
[{"category": "symptom", "value": "পিপাসা", "polarity": "present"}]
```

| Measurement | Definition |
| --- | --- |
| WER/CER | Edit-distance errors against a human-verified transcript; WER can exceed 100% |
| Text normalization | NFC, lowercase, Bengali digits to ASCII, punctuation/symbols to spaces; CER excludes whitespace; no automatic spelling fixes |
| DER | 10 ms frame approximation, optimal speaker permutation, zero collar, overlapping reference speech excluded; not directly comparable to published collar-based DER |
| Role accuracy | Time-weighted doctor/patient accuracy on non-overlap annotated reference speech; unknown predictions count as wrong |
| Fact F1 | Exact normalized category/value/polarity set matching; no semantic LLM judge or synonym expansion |
| Latency | Backend decode-start to final result, including model loads; upload duration is a separate browser observation |
| First STT segment | Backend start to first decoded segment; not live speech latency |
| RTF | Total processing seconds / analyzed audio seconds |
| Memory | Sampled server-process RSS, not total machine memory or a guaranteed limit |
| Calls | Separate local STT/diarization invocations and outbound LLM HTTP attempts; status polling is not a model API call |
| Cost | Token-based estimate only when both provider rates and usage exist; otherwise null/unknown; local electricity/hardware not priced |

Set actual provider rates in `.env` as `LLM_INPUT_USD_PER_MILLION` and `LLM_OUTPUT_USD_PER_MILLION`. Do not assume zero because Cline displayed $0. Unknown pricing does not prevent testing.

## Reproducibility and reports

Each run is identified by a UUID and saves `job.json`, `result.json`, and (when entered) `reference.json` in `data/runs/<id>/`. Results include source SHA-256, clip boundaries, noise seed/SNR, decoding strategy, speaker count, model revision/hashes, package versions, thread count, wall timings, invocation ledger and token usage.

Open completed runs to populate the comparison table, then export CSV. Download JSON for the run audit record and any saved evaluation reference. Backend run JSON does not embed source audio: retain the source file separately and verify its SHA-256. Compare only the same source/clip/reference when assessing a strategy change. Temperature zero reduces sampling variability but is not a guarantee of deterministic provider output. A single recording is a smoke test, not proof of general Bengali clinical accuracy.

## Tests

Run backend regression tests:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

The original browser collection checks remain at `/test.html` and use a separate IndexedDB database. See TEST-RESULTS.md for the earlier collection tests; see BENCHMARK-TEST-RESULTS.md for v2 verification and real-run limits. Runtime dependencies are listed in requirements.txt; a pinned installed-environment snapshot is provided after verification.

## Security and data handling

- `.env`, recordings, runs, model weights and Python environments are excluded by `.gitignore`.
- Only explicit static assets are served; `.env`, `.git`, source code, uploads and arbitrary filesystem paths are not exposed.
- Server binds to loopback; mutation requests from other origins are rejected.
- API keys stay on the backend. Provider redirects are not followed, response bodies are withheld on provider errors, and the key is never included in run exports.
- Uploads are limited to 50 MB and analyzed clips to 20 minutes on this configuration.
- This is a local research tool, not a hosted clinical system: no authentication, database encryption, clinical decision support or production compliance certification is claimed.

## Troubleshooting

| Problem | Action |
| --- | --- |
| Backend unavailable | Run START-BENCHMARK.cmd, not the old standalone static server |
| Port 8787 busy | Use the free port printed by the launcher; current test server is on 8788 |
| Models not ready | Run setup; check MODELS_DIR and available drive space |
| First run slow | Model loading and CPU transcription take time; inspect run stage and processed-audio time |
| LLM HTTP 401/403 | Verify the provider key and access; a proxy key is not necessarily valid on the model vendor's official API |
| Provider cost unknown | Enter actual provider token rates; this is not an inference failure |
| Roles look wrong | Inspect diarization and transcript first, then review LLM evidence; do not treat predictions as ground truth |
| High WER | Check exact reference/clip matching, audio quality, domain vocabulary and model suitability |
| Browser changed | Collection IndexedDB is browser/origin-specific; server run history is separate |

## Important files

- `benchmark.html`, `benchmark.js`, `benchmark.css`: benchmark interface.
- `backend/`: API, pipeline, schema/evidence validation and evaluation.
- `scripts/prepare_models.py`: model preparation and manifest generation.
- `tests/test_backend.py`: regression tests.
- `index.html`, `app.js`, `style.css`: original collection studio.
- `START-BENCHMARK.cmd`, `SETUP-BACKEND.cmd`: launch/setup.
- `.env.example`: shareable configuration template.

Runtime storage update (12 November 2026): .venv, .runtime and .bootstrap now use directory junctions to E:/MedDesk-model-cache/project-runtime/. Their original project paths still work. Keep that E: folder; it contains required Python dependencies, not disposable cache. Code, .env, source audio, model weights and run results were preserved.


## CPU model comparison — 13 November 2026

See [STT-MODEL-COMPARISON.md](STT-MODEL-COMPARISON.md) for measured speed, RAM, provisional reference error rates and the real Hermes review. Run `.venv\Scripts\python.exe scripts\compare_stt.py` to repeat the local-only development comparison on the supplied 113-second scope. Each model uses a separate process; failures remain failures. This script is specific to the supplied conversation/reference; it does not silently label arbitrary scripts as ground truth.

ONNX models always split uploaded recordings internally at quiet boundaries near 15 seconds to bound working memory. Single-file mode therefore describes one submitted job, not necessarily one neural decoder invocation. The ledger records actual local decoder calls. These chunks are not live microphone streaming.

To install an alternative ONNX model: `.venv\Scripts\python.exe scripts\prepare_models.py --profile indicconformer`. Whisper conversion still requires a separate conversion environment with CPU Torch, Transformers and CTranslate2; normal setup no longer installs those heavy tools. Configure `DEFAULT_STT_PROFILE` to change the API default.

The current laptop can run the complete Zipformer → speaker clustering → Mistral pipeline. This does not certify transcript, medical-fact or identity accuracy. Speaker DER and role/fact accuracy require their own human annotations. A nearby script-derived reference is marked provisional until its verbatim wording and endpoint match the exact audio.

Developer checks: `.venv\Scripts\python.exe -m pytest tests -q --basetemp=data/test-temp`. `pytest.ini` restricts collection to project tests and excludes runtime/tool caches. Frontend and backend sources are formatted; recognition adapters live in `backend/stt.py`, orchestration in `backend/pipeline.py`, scoring in `backend/evaluation.py` and provider access in `backend/llm.py`.


## Live conversation, noise removal and voice signatures

These features are implemented and enabled when their model files are ready. See [FEATURE-VERIFICATION.md](FEATURE-VERIFICATION.md) for actual tests and limits.

- **Live conversation:** give recording permission, choose final options, and click Start live microphone. AudioWorklet sends mono 16-bit PCM at 16 kHz over `/api/live`. Stop & analyze closes microphone tracks, flushes the decoder and hands the saved WAV to final analysis. A 20-minute session limit, two-second maximum frame size, bounded WebSocket queue and client backpressure protect this CPU setup. Refresh/disconnect cancels an incomplete capture; finalized runs persist.
- **GTCRN noise removal:** select Apply local GTCRN noise removal before a batch or live-final run. Original source is preserved. Results include enhanced clip playback. Synthetic-noise experiments also record before/after same-timeline SNR and SI-SDR using the original recording as a surrogate clean reference; these metrics are not real-clinic accuracy. Enhancement can harm intelligibility, so it is optional.
- **Voice signatures:** upload 3–30 seconds of a single speaker, provide name/role and explicit biometric consent. Prefer 10–20 seconds of clear speech. Local VAD rejects insufficient speech. A normalized ERes2Net embedding and profile metadata are Fernet-encrypted. On Windows the encryption key is itself wrapped by current-user DPAPI. Raw temporary enrollment files are deleted after processing, including failures.
- **Matching:** enable Match against enrolled voice signatures. Non-overlapping speaker audio is compared by cosine similarity. Initial threshold 0.70 and top-two margin 0.10 are conservative defaults, not calibrated guarantees. Unknown/ambiguous matches stay unknown. Enrolled role metadata and LLM-inferred conversation roles are displayed separately. No speaker verification/liveness or anti-spoofing claim is made.
- **Deletion/privacy:** Delete signature removes the biometric template from the active encrypted store. Historical benchmark reports retain their audit labels/similarity results, not embeddings. Neither templates nor local profile metadata are sent to the LLM, including extraction-only retries. Recorded words may still contain names; transcript sharing remains separately permission-gated.
- **Keys/portability:** Windows profile storage is bound to the Windows account. Re-enroll on another computer/account; do not expect copying DPAPI files to unlock them there. Non-Windows deployments must set a Fernet `VOICE_ENCRYPTION_KEY` in protected server configuration. Keys/templates are never served as static assets. Run one backend process per workspace; this loopback research app is not a public multi-user service.

`SETUP-BACKEND.cmd` now also runs `scripts/prepare_feature_models.py` for the small Vosk INT8 streaming and GTCRN assets. It records pinned revision and model hashes in `MODELS_DIR/feature-manifest.json`. The original final ASR remains Zipformer by default because the streaming model was less accurate on the provisional script comparison.

Developer tests: install `requirements-dev.txt` for Playwright and Ruff. Browser checks use installed Chrome, not a downloaded browser. `scripts/test_feature_integration.py` exercises real local models and a real WebSocket; `scripts/browser_features.py` exercises AudioWorklet and the microphone path with controlled fake audio. Both create uniquely marked temporary profiles and delete them. Such same-source smoke tests prove the feature path, not identification accuracy.
