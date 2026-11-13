> Latest implemented features and 48-test verification: [FEATURE-VERIFICATION.md](FEATURE-VERIFICATION.md).

> Updated CPU-model comparison and 13 November tests: [STT-MODEL-COMPARISON.md](STT-MODEL-COMPARISON.md). The dated results below are historical.

# Benchmark v2 — verification report

Date: **10 November 2026**. Local Windows CPU testing; configured Mistral model through Xkiro. No API key or private transcript is included in this report.

## Automated checks

- **30 backend regression tests passed**: Bengali normalization/edit distance, bounded decoding, noise SNR/seed, timestamps and invocation counts, diarization permutation, role/fact evidence, ground-truth gates, provider cost/error handling, upload/host/origin/private-file protection and single-worker concurrency.
- Headless installed Chrome: desktop interface, mobile overflow, unverified script loading, source selection and no JavaScript exceptions passed.
- Existing collection integration page: **ALL 10 CHECKS PASSED**.
- Real-result workflow: tabs, per-utterance source playback metadata, saved unverified reference, reload and report download passed using a marked test copy; actual inference runs were preserved.
- Safe launcher selection/reuse passed: the existing port-8787 service was preserved and this workspace was started/reused on 8788. PowerShell setup syntax and Python compilation passed. Installed runtime versions are pinned in requirements.lock.txt.
- Model/profile readiness and credential leakage scans passed. .env, audio, conversation, models, data and environments are ignored by Git.

## Actual supplied-audio smoke runs

These demonstrate execution, not independently measured clinical accuracy. Earlier runs used different decoder settings; this is not a fair accuracy leaderboard.

| Run | Status | Total seconds | Peak server RSS MB | Local STT invocations | LLM HTTP attempts |
| --- | --- | ---: | ---: | ---: | ---: |
| BanglaASR, 120 s, local only | completed | 116.212 | 781.8 | 1 | 0 |
| BanglaASR, complete 509.8 s recording, initial attempt | partial | 509.926 | 633.4 | 1 | 1 |
| Vivasoft, 120 s, final decoder + LLM | completed | 88.89 | 659.0 | 1 | 1 |
| Full-transcript extraction-only retry, final evidence filtering | completed | 33.95 | not sampled | 0 | 1 |

The final 120-second run had STT 67.073 s, diarization 11.464 s, LLM 9.999 s and RTF 0.741. Both doctor and patient roles were produced. These are model predictions, not verified role accuracy.

The complete recording was decoded/transcribed and diarized. Its first LLM response failed strict schema validation; the parent run remains partial. JSON mode and explicit evidence filtering were subsequently verified. A separate extraction-only child run completed with 33 retained cited facts and doctor/patient roles. No hidden retry was made, and extraction-only latency is not reported as full-pipeline latency.

## Chunk/noise and status-transport checks

| Experiment, first 30 seconds, Vivasoft | Status | Seconds | Local STT invocations | LLM calls |
| --- | --- | ---: | ---: | ---: |
| chunks_clean | completed | 35.67 | 2 | 0 |
| batch_noise_20db | completed | 18.024 | 1 | 0 |

SSE delivered a real job event and HTTP polling observed completion. White-noise experiment used 20 dB SNR, seed 42. Unit tests independently verified the injected SNR. Lower latency on a noisy sample does not establish better recognition.

## Observed issues and fixes

- C: had little free space. Model and conversion assets were installed on E:/MedDesk-model-cache; no unrelated user files were removed.
- Windows paging limits interrupted a second-model conversion. FP16 low-memory loading in a separate conversion environment succeeded after active inference finished.
- The Bengali checkpoint lacked tokenizer.json; its own fast tokenizer was generated from its vocabulary/merges rather than borrowing a different vocabulary.
- Long LLM output initially failed the schema. JSON mode, field-level validation diagnostics and explicit audited extraction-only retries were added and tested.
- Invalid role evidence IDs are discarded. A role is retained only if valid same-speaker evidence remains; otherwise it becomes unknown.
- Text-only decoding with separate cross-attention word alignment improved the final short-run processing time. Recognition errors remain.

## Accuracy and completion limits

- The supplied DOCX is a reading script, not a human-verified transcript. **No real WER/CER, DER, role-accuracy percentage or fact-F1 claim has been made.** Those scoring implementations are regression-tested, but require matching verified references.
- Bengali transcription contains word errors/omissions. Downstream cited facts can still be semantically wrong; evidence checks do not replace human review. Neither profile is established as the best Bengali clinical model.
- Token counts and call attempts are recorded. Provider prices were not configured, so USD cost remains null/unknown. This is not a zero-cost claim.
- This version supports recorded-file batch/chunk processing and SSE/polling for job status. **Live WebSocket ASR, online speaker tracking and denoising models are not implemented.** Noise injection is an experiment, not noise removal.
- No known-person voiceprint enrollment/identification is implemented; speaker diarization and doctor/patient role inference are different tasks.
- It is a local research/benchmark workspace, not a production clinical decision system. Microphone sound quality was previously checked by the user; current automation used files, not a new live microphone recording.
- Fresh-machine setup was not tested on a second computer. This computer’s environments, conversions and launch server were exercised.

## Reproduce

Run START-BENCHMARK.cmd and open the address it prints (normally port 8787; current delivered server uses 8788). Test services used port 8788 during verification to preserve the existing server. Use the same source audio, clip, model manifest, decoding settings, noise seed and reference for controlled comparisons. Detailed run JSON and test screenshots remain in the ignored data/ folder. Private source audio is not embedded in backend reports.

Full operating instructions: README.md and USER-GUIDE-BN.md.

## Progress recovery fix — 11 November 2026

The reported stalled BanglaASR run `9cf09fb91a0849a3ac9e62f896a1512d` was already completed by the backend in 148.768 seconds; there was no active inference job. Browser progress could remain stale after SSE disconnected because the old error handler stopped monitoring.

Added SSE error fallback to polling, a five-second safety check even when SSE remains open but silent, retry after temporary status-fetch failures, request timeouts, tab-focus recovery and selected-run restoration on reload. Run links can select a saved result with `?run=<id>`. None of these checks restarts inference or adds LLM calls.

Headless Chrome regression tests passed for disconnected SSE, silently stalled SSE and one failed polling request. Every case reached completed and restored the selected result after reload. The original completed run was not modified.
