> Subsequent live/enhancement/identity implementation and tests: [FEATURE-VERIFICATION.md](FEATURE-VERIFICATION.md). The model comparison below remains a provisional development comparison.

# Bengali STT comparison — 13 November 2026

Five CPU candidates were executed against the supplied conversation. **Zipformer INT8 is the practical default for this laptop. No universal or verified clinical accuracy winner is claimed.**

## Measured local results

| Candidate | Status | STT seconds | Peak worker RSS MB | Provisional WER | Provisional CER |
| --- | --- | ---: | ---: | ---: | ---: |
| zipformer | completed | 8.324 | 323.0 | 44.12% | 32.69% |
| indicconformer | completed | 47.075 | 358.9 | 52.52% | 33.85% |
| vivasoft | completed | 209.367 | 585.0 | 74.37% | 49.56% |
| vosk_streaming | completed | 7.566 | 156.7 | 55.04% | 40.74% |
| bangla_asr | failed | 1.634 | 513.0 | not scored | not scored |

Lower WER/CER is better. These are **distances from a provisional script subset**, not certified transcription accuracy. Do not report `100 − WER` as clinical accuracy.

The user said the first two minutes were checked and authorized choosing a nearby dialogue boundary. We fixed the clip at 113 seconds, ending after the patient’s foot-tingling answer and before the next wound question. The boundary was estimated from earlier timestamps. The evaluator did not independently listen to establish exact wording. Differences are apparent between the script and generated transcripts, including consent phrasing, extra spoken words and weight details; a script can therefore penalize faithfully spoken deviations. Confirm an exact verbatim reference before using the ranking as accuracy evidence.

All candidates received the same original audio scope. ONNX short-context models use quiet boundaries near 15 seconds; Whisper uses fixed 15-second windows with VAD. This is a comparison of runnable model pipelines, not a controlled architecture-only ablation. Zipformer/IndicConformer used four threads; Vivasoft completed its low-memory retry with one. The Vosk research probe used two threads and one second of trailing silence for flushing. These settings are recorded, not treated as identical latency conditions.

Initial Whisper attempts failed with `mkl_malloc: failed to allocate memory`. Vivasoft completed after disabling MKL buffer pooling and limiting threads. The BanglaASR retry exited with code 1 without a new result; its cause was not established. Its row above preserves the original failed attempt, not a fabricated score. The backend now disables MKL fast-memory pools before CTranslate2 import and uses a separate two-thread Whisper budget.

## Final full pipeline verification

Run `4b6385756eaa4b7198fe9158e0910683` completed on the 113-second clip with Zipformer → local speaker clustering → configured Xkiro/Mistral role and fact extraction.

- Total: **34.1 s**; STT 6.714 s; diarization 10.231 s; LLM 16.792 s.
- Peak server process RSS: **375.7 MB**. This is process memory, not total laptop RAM.
- Actual calls: 8 local decoder invocations, 1 local diarization invocation, 1 LLM HTTP request.
- Doctor and patient roles were returned with evidence; 18 quoted facts survived schema/evidence checks. These checks do not prove semantic correctness.
- Provider cost remains unknown because actual provider pricing is not configured. No zero-cost assumption.
- DER, role accuracy and fact F1 remain unscored without their independent human annotations.

## Verification and artifacts

- 34 backend regression tests passed; Python compilation and Ruff unused-import checks passed.
- Installed Chrome: desktop/mobile layout, supplied-script draft state, source selection, real-result rendering, tabs, unverified reference persistence, run download and source playback metadata passed; no JavaScript exceptions.
- Existing recording collection integration: ALL 10 CHECKS PASSED. Browser automation did not claim to verify a new real microphone recording by ear.
- A real 10-second WAV upload completed the local pipeline with zero external LLM calls.
- Chrome recovery after disconnected SSE, silent SSE and a failed polling request passed; reload restored the selected run.
- Actual 30-second clean-chunk and 20 dB synthetic-white-noise runs completed with zero LLM requests. SSE events and HTTP polling were exercised. This is not a denoising-quality test.
- Model weight revisions and SHA-256 hashes are recorded in per-profile manifests. Runtime/test packages are pinned in requirements.lock.txt.
- Real Hermes Agent review completed; see [HERMES-REVIEW.md](HERMES-REVIEW.md). Supporting artifacts are in ignored data/hermes-review/.
- Local comparison outputs: data/model-comparison/. Full runs: data/runs/. Screenshots: data/ui-tests/. No audio/key is embedded in this public report.

## Models investigated

- [Bengali Zipformer INT8](https://huggingface.co/SayedShaun/bangla-zipformer-onnx), CC BY-SA 4.0 weights. Default; preserve upstream attribution/license when redistributing.
- [Bengali IndicConformer ONNX](https://huggingface.co/OpenVoiceOS/ai4bharat-indicconformer-bn-onnx), MIT model card.
- [Vivasoft Bengali Whisper](https://huggingface.co/vivasoft/whisper-small-bn) and [BanglaASR](https://huggingface.co/bangla-speech-processing/BanglaASR), existing CTranslate2 INT8 profiles.
- [Small Bengali streaming Vosk INT8](https://huggingface.co/bbbipul/vosk-small-streaming-bn-int8), Apache 2.0. Now used for live WebSocket drafts; final analysis still defaults to Zipformer.
- [Intel MKL memory-manager documentation](https://www.intel.com/content/www/us/en/docs/onemkl/developer-reference-c/2026-2/mkl-disable-fast-mm.html) supports the memory-pool setting; it can trade speed for lower retained buffers.

## Remaining validation boundary

The working software and resource tests are complete for the scenarios above. A claim of best Bengali/clinical accuracy still needs an exact human-verified transcript, timed speaker/role labels, expected facts, and multiple unseen conversations. Live WebSocket ingestion, encrypted identity enrollment and optional GTCRN denoising were subsequently implemented; see FEATURE-VERIFICATION.md. Online speaker-role updates during speech are not claimed.
