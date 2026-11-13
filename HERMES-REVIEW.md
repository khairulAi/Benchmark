# Hermes review — 13 November 2026

The real installed **NousResearch Hermes Agent** was run with the configured Xkiro/Mistral model after the user explicitly approved sending project source for review. No audio or API key was included in the review prompt. Hermes completed successfully (exit 0, 81.97 seconds); raw output and invocation metadata are under ignored `data/hermes-review/`.

The launcher had an incomplete dependency update. The review used Hermes's existing committed Python environment with a separate Hermes home. The temporary review gateway was identified by its own home, PID and creation time and stopped after completion; the user's normal Hermes gateway/configuration was not changed.

## Changes accepted after verification

- Release recognition models in `finally`, including failure paths.
- Mark failed local decoder calls as failed and retain their elapsed time.
- Separate STT adapters from pipeline orchestration.
- Use bounded inputs for short-context ONNX models and preserve acoustic token timestamps with original offsets.
- Compare actual target audio before selecting a default; report model manifests and reference limitations.

## Suggestions checked and not applied

- `num_workers=0` was not adopted as a supported way to disable CTranslate2 threads.
- A `random_state` option was not added to sherpa's diarization configuration; it is not an exposed setting in the installed API.
- Whisper DTW word alignment was retained. `without_timestamps=True` is not proof that DTW word timestamps are missing.
- The declared CER whitespace policy was retained instead of changing the scoring definition during comparison.
- An arbitrary five-minute limit was not imposed on already bounded audio decoding. ONNX inference windows are capped separately.

Agent review is supporting evidence, not a substitute for execution tests or human reference annotation. The final implementation is verified by regression tests, actual local model runs and Chrome workflow checks described in STT-MODEL-COMPARISON.md.


## Remaining features — second Hermes implementation review

A second real Hermes run completed successfully (exit 0, **52.80 seconds**) over `feature_routes.py`, `streaming.py`, `voices.py` and `enhancement.py`. Its source-only prompt requested concrete patches and meaningful tests; no audio, profile templates or API key was part of the prompt. Artifacts: `data/hermes-features-review/`.

Verified improvements include explicit same-origin WebSocket requirements, control-character rejection in names, serialized key creation, encrypted temporary-file cleanup and regression coverage for disconnect cleanup/handoff. Independent inspection also found that extraction-only retries could otherwise forward identity metadata; provider input is now explicitly whitelisted and a regression test protects this boundary.

Some agent findings described protections already present (odd PCM-byte rejection, model garbage collection, bounded padding, shared reservation locks). They were not accepted as bugs. Its proposed per-message timing throttle would reject legitimate buffered transport and was not applied; bounded frames, total duration, socket queue limits and client backpressure are used instead. The review was checked against actual code and execution results.
