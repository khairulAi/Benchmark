# Feature verification — 13 November 2026

Implemented: live WebSocket microphone ASR, optional local GTCRN enhancement, and encrypted cross-recording speaker enrollment/matching. Human reference annotation and accuracy sign-off remain separate.

## Actual tests

- **48 backend tests passed.** New checks cover biometric consent, invalid profile names, encrypted storage and deletion, atomic-write failure recovery, silent audio, ambiguous/incompatible voice rejection, WebSocket origins, disconnect cleanup, atomic final-job handoff, known-SNR calculations, and prevention of identity metadata reaching the LLM on any extraction path.
- Real model integration: temporary single-speaker enrollment, encrypted storage, no raw temporary enrollment file after processing, same-source voice match, enhanced-audio endpoint, signature deletion, actual PCM WebSocket partial transcript before Stop, and completed final analysis passed.
- Installed Chrome: voice-enrollment/deletion UI and AudioWorklet → WebSocket → partial text → Stop → final analysis passed. The controlled fake-microphone capture was **7.772 seconds**. This exercises the browser microphone code path, not real hardware listening quality.
- Chrome reload restored the finalized run and enhanced-audio controls. Desktop/mobile layouts passed; a real-result grid overflow found during testing was fixed. No JavaScript exceptions.
- Existing batch UI, unverified reference persistence, source playback metadata, report download and original recording studio **ALL 10 CHECKS PASSED** remain passing.

## Measured runs

| Scenario | Result | Final processing seconds | Peak process RSS MB |
| --- | --- | ---: | ---: |
| 10 s same-source identity + enhancement smoke | completed | 4.528 | 365.3 |
| 20 s accelerated PCM WebSocket replay, then local enhanced final analysis | completed | 6.394 | 397.5 |
| 113 s Bengali, injected 20 dB noise + GTCRN + final STT/speakers/Mistral | completed | 42.753 | 453.0 |

The 113-second run `eec5bb4d60e140bfb6cf4e7ef61aa931` used 8 local STT invocations, one denoiser invocation, one diarization invocation and **1 provider request**. It returned doctor/patient roles and 19 evidence-checked facts. Those are unverified model predictions. No profiles remained after test deletion, so identity matching correctly reported no enrolled profiles rather than inventing names.

The WebSocket replay intentionally sent prerecorded PCM faster than real time. Its server-ingress first-text timing is not conversational end-to-end latency. Chrome separately exercised paced capture with a controlled fake microphone. Final ASR is a second pass and is counted separately from live decoder steps.

## Noise quality observation

For the 20 dB injected-white-noise experiment, same-timeline signal SNR was **20.000 dB before** enhancement and **12.829 dB after**; SI-SDR was 20.000 and 13.065 dB. These metrics use the original recording as a surrogate clean reference, which also includes its original background sound. They do **not** establish an improvement; enhancement may remove or alter speech/background components. Consequently denoising remains **off by default**, is never silently applied, and original/enhanced playback is available for review. No denoising superiority or clinical accuracy is claimed.

## Voice identity boundaries

The same-source smoke match proves the matching path, not accuracy on unseen speech. Signatures are normalized 512-dimensional ERes2Net embeddings after local speech detection. Profile vectors and metadata are Fernet-encrypted; the local Windows key is protected with current-user DPAPI. The initial similarity threshold and ambiguity margin are configurable and need target-data calibration. Unknown speakers, short speech and ambiguous matches are not forced into a known identity. No anti-spoofing or authentication guarantee is made.

Temporary test profiles were deleted. Raw enrollment upload files are removed after processing. Historical benchmark labels remain as audit metadata; embeddings are not copied into run JSON or provider requests. The source recordings already supplied for benchmarking remain separate from enrollment.

## Hermes implementation review

A second real **NousResearch Hermes Agent** run through the configured Xkiro/Mistral endpoint completed in **52.80 seconds** over four new source modules. Verified suggestions were applied; unsupported/already-satisfied claims were rejected after inspection. See [HERMES-REVIEW.md](HERMES-REVIEW.md). Only authorized source code was sent for review, not audio, signatures or keys.

## Reproduce and inspect

- Run `START-BENCHMARK.cmd`; open the printed local address.
- New controls: Apply local GTCRN noise removal, Match against enrolled voice signatures, Live conversation and Voice signatures.
- Backend: `.venv\Scripts\python.exe -m pytest tests -q --basetemp=data/test-temp`.
- Real feature integration: `.venv\Scripts\python.exe scripts/test_feature_integration.py`.
- Chrome feature workflow: `.venv\Scripts\python.exe scripts/browser_features.py` (install requirements-dev.txt; installed Chrome required).
- Detailed local evidence: `data/feature-tests/integration.json`, `browser.json`, screenshots and run JSON. Private artifacts are excluded from Git.
- Model versions/hashes: `MODELS_DIR/feature-manifest.json` and per-STT manifests.

Remaining human work: exact transcript verification, timed speaker/role reference, expected clinical facts, threshold calibration and unseen-conversation accuracy evaluation. Live drafts do not perform online speaker-role updates; that analysis is finalized after Stop.
