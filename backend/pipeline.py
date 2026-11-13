from __future__ import annotations
import gc
import importlib.metadata
import json
import os
import platform
import threading
import time
from pathlib import Path
import numpy as np
import psutil
from . import settings as cfg
from .core import atomic_json, bind_words, sha256
from .llm import extract

from .stt import transcribe as stage_stt, model_ready

PIPELINE_SOURCE_HASH = sha256(Path(__file__))


def stage_speakers(audio, num_speakers, update):
    import sherpa_onnx as s

    config = s.OfflineSpeakerDiarizationConfig(
        segmentation=s.OfflineSpeakerSegmentationModelConfig(
            pyannote=s.OfflineSpeakerSegmentationPyannoteModelConfig(
                model=str(cfg.SEGMENTATION), window_shift_ratio=0.5
            ),
            num_threads=cfg.THREADS,
            provider="cpu",
        ),
        embedding=s.SpeakerEmbeddingExtractorConfig(
            model=str(cfg.EMBEDDING), num_threads=cfg.THREADS, provider="cpu"
        ),
        clustering=s.FastClusteringConfig(num_clusters=num_speakers, threshold=0.5),
        min_duration_on=0.3,
        min_duration_off=0.5,
    )
    if not config.validate():
        raise RuntimeError("Diarization weights/config invalid; run model setup")
    model = s.OfflineSpeakerDiarization(config)

    def progress(done, total):
        update("diarizing", {"diarization_progress": round(done / max(total, 1), 3)})
        return 0

    try:
        result = model.process(audio, callback=progress).sort_by_start_time()
        return [
            {
                "start": float(turn.start),
                "end": float(turn.end),
                "speaker": f"speaker_{turn.speaker:02d}",
            }
            for turn in result
        ]
    finally:
        del model
        gc.collect()


def run_pipeline(run_id, source, options, update):
    from .audio import decode_clip, add_noise

    result = {
        "id": run_id,
        "schema_version": 2,
        "status": "running",
        "created_at": time.time(),
        "options": options,
        "ledger": [],
        "warnings": [],
        "timings": {},
        "metrics": None,
        "transcript": [],
        "extraction": None,
    }
    output = cfg.DATA / "runs" / run_id / "result.json"
    start = time.perf_counter()
    done = threading.Event()
    result["resources_at_start"] = {
        "available_ram_mb": round(psutil.virtual_memory().available / 1024**2, 1)
    }
    peak = [psutil.Process().memory_info().rss]

    def sample():
        while not done.wait(0.25):
            peak[0] = max(peak[0], psutil.Process().memory_info().rss)

    monitor = threading.Thread(target=sample, daemon=True)
    monitor.start()

    def save_stage(stage, extra=None):
        if (
            extra
            and extra.get("processed_audio_seconds")
            and "first_stt_segment_seconds" not in result["timings"]
        ):
            result["timings"]["first_stt_segment_seconds"] = round(
                time.perf_counter() - start, 3
            )
        result["stage"] = stage
        result.update(extra or {})
        atomic_json(output, result)
        update(stage, extra or {})

    try:
        model_id, model_path = cfg.STT_PROFILES[
            options.get("stt_profile", "bangla_asr")
        ]
        if (
            not model_ready(options.get("stt_profile", "bangla_asr"), model_path)
            or not cfg.SEGMENTATION.exists()
            or not cfg.EMBEDDING.exists()
        ):
            raise RuntimeError(
                "Selected speech models missing. Run model setup for this profile."
            )
        save_stage("decoding")
        audio, original_seconds = decode_clip(
            source, options["offset_seconds"], options["max_seconds"]
        )
        result["audio"] = {
            "filename": source.name,
            "sha256": sha256(source),
            "original_seconds": round(original_seconds, 3)
            if original_seconds
            else None,
            "clip_offset_seconds": options["offset_seconds"],
            "analyzed_seconds": len(audio) / 16000,
            "sample_rate": 16000,
            "channels": 1,
            "timestamps": "relative to analyzed clip; add clip_offset_seconds for original recording",
        }
        if len(audio) < 16000:
            raise RuntimeError("At least one second of audio required")
        if len(audio) > 16000 * 1200:
            raise RuntimeError("Select a clip of 20 minutes or less on this CPU setup")
        if not np.isfinite(audio).all():
            raise RuntimeError("Invalid audio samples")
        result["audio"]["rms"] = float(np.sqrt(np.mean(audio**2)))
        result["audio"]["clipped_sample_fraction"] = float(
            np.mean(np.abs(audio) >= 0.999)
        )
        if result["audio"]["rms"] < 0.001:
            result["warnings"].append("Very quiet audio; recognition may be unreliable")
        clean_reference = (
            audio
            if options.get("denoise") and options["noise_snr_db"] is not None
            else None
        )
        if options["noise_snr_db"] is not None:
            audio, result["audio"]["noise"] = add_noise(audio, options["noise_snr_db"])
        result["timings"]["decode_seconds"] = round(time.perf_counter() - start, 3)
        identity_audio = audio
        if options.get("denoise"):
            from .enhancement import enhance
            import soundfile

            save_stage("denoising")
            tick = time.perf_counter()
            audio = enhance(audio, result["ledger"])
            soundfile.write(
                output.parent / "enhanced.wav", audio, 16000, subtype="PCM_16"
            )
            result["timings"]["denoise_seconds"] = round(time.perf_counter() - tick, 3)
            result["audio"]["enhancement"] = {
                "model": "GTCRN",
                "source_preserved": True,
                "audio_url": f"/api/runs/{run_id}/enhanced-audio",
            }
            if clean_reference is not None:
                from .enhancement import synthetic_metrics

                result["audio"]["enhancement"]["synthetic_reference_metrics"] = {
                    "before": synthetic_metrics(clean_reference, identity_audio),
                    "after": synthetic_metrics(clean_reference, audio),
                    "method": "Original recording as surrogate clean reference; injected noise only; same timeline, no alignment adjustment. Not clinical-noise accuracy.",
                }
            result["warnings"].append(
                "Denoising can remove speech detail; compare original and enhanced output. Accuracy improvement is not assumed."
            )
        tick = time.perf_counter()
        result["asr_segments"] = stage_stt(
            audio,
            save_stage,
            result["ledger"],
            options["strategy"],
            options["chunk_seconds"],
            model_path,
            options.get("stt_profile", "bangla_asr"),
        )
        result["timings"]["stt_seconds"] = round(time.perf_counter() - tick, 3)
        if not result["asr_segments"]:
            raise RuntimeError("No speech transcript returned")
        save_stage("diarizing")
        tick = time.perf_counter()
        diar_call = {
            "stage": "diarization",
            "call_kind": "local_inference",
            "status": "requested",
        }
        result["ledger"].append(diar_call)
        try:
            result["speaker_segments"] = stage_speakers(
                audio, options["num_speakers"], save_stage
            )
            diar_call["status"] = "completed"
        except Exception:
            diar_call["status"] = "failed"
            raise
        finally:
            diar_call["latency_seconds"] = round(time.perf_counter() - tick, 3)
        result["timings"]["diarization_seconds"] = round(time.perf_counter() - tick, 3)
        result["transcript"] = bind_words(
            result["asr_segments"], result["speaker_segments"]
        )
        result["warnings"].append(
            "Speaker labels are per-run clusters, not verified identities. Roles and extraction are model drafts requiring review."
        )
        if options["use_llm"]:
            save_stage("extracting")
            tick = time.perf_counter()
            try:
                result["extraction"], warnings = extract(
                    result["transcript"], result["ledger"]
                )
                result["warnings"].extend(
                    warnings + result["extraction"].get("warnings", [])
                )
                role_map = {
                    r["speaker"]: r["role"] for r in result["extraction"]["roles"]
                }
                for utterance in result["transcript"]:
                    utterance["role"] = role_map.get(utterance["speaker"], "unknown")
            except RuntimeError as error:
                result["llm_error"] = str(error)
                result["warnings"].append(
                    "LLM failed; STT and speaker outputs preserved. See llm_error."
                )
            result["timings"]["llm_seconds"] = round(time.perf_counter() - tick, 3)
        if options.get("identify_voices"):
            from .voices import identify

            save_stage("identifying")
            tick = time.perf_counter()
            try:
                result["voice_matches"], warnings = identify(
                    identity_audio, result["speaker_segments"], result["ledger"]
                )
                result["warnings"].extend(warnings)
                # Attach identities only AFTER LLM extraction. Biometric templates,
                # profile names and similarities are never sent to the provider.
                for utterance in result["transcript"]:
                    utterance["voice_identity"] = result["voice_matches"].get(
                        utterance["speaker"], {"status": "unknown"}
                    )
            except RuntimeError as error:
                result["identity_error"] = str(error)
                result["warnings"].append(
                    "Identity matching failed; transcript and extraction preserved."
                )
            result["timings"]["voice_identification_seconds"] = round(
                time.perf_counter() - tick, 3
            )
        result["status"] = (
            "partial"
            if result.get("llm_error") or result.get("identity_error")
            else "completed"
        )
    except Exception as error:
        result["status"] = "failed"
        # Do not serialize provider response bodies, headers, credentials or traceback paths.
        result["error"] = (
            str(error)
            if isinstance(error, RuntimeError)
            else f"{type(error).__name__}: processing failed; consult local logs without exposing credentials."
        )
    finally:
        done.set()
        monitor.join(timeout=1)
        result["timings"]["total_seconds"] = round(time.perf_counter() - start, 3)
        duration = result.get("audio", {}).get("analyzed_seconds")
        result["timings"]["real_time_factor"] = (
            round(result["timings"]["total_seconds"] / duration, 3)
            if duration
            else None
        )
        result["peak_process_rss_mb"] = round(peak[0] / 1024**2, 1)
        result["calls"] = {
            "stt_local_invocations": sum(e["stage"] == "stt" for e in result["ledger"]),
            "llm_http_attempts": sum(e["stage"] == "llm" for e in result["ledger"]),
            "diarization_local_invocations": sum(
                e["stage"] == "diarization" for e in result["ledger"]
            ),
            "note": "Local invocations are not paid HTTP API calls. Internal decoder windows are not counted as separate API requests.",
        }
        result["calls"]["denoise_local_invocations"] = sum(
            e["stage"] == "denoise" for e in result["ledger"]
        )
        result["calls"]["voice_identification_local_invocations"] = sum(
            e["stage"] == "voice_identification" for e in result["ledger"]
        )
        if options.get("streaming_context"):
            result["live_stream"] = options["streaming_context"]
            result["calls"]["live_stt_decoder_steps"] = options["streaming_context"][
                "decoder_steps"
            ]
            result["warnings"].append(
                "Live draft inference and final ASR are separate passes. Live decoder steps are reported separately from final local STT calls and paid HTTP calls."
            )
        costs = [e.get("cost_usd") for e in result["ledger"] if e["stage"] == "llm"]
        result["cost_usd"] = (
            sum(costs) if costs and all(c is not None for c in costs) else None
        )
        result["cost_note"] = (
            "Local CPU runtime/electricity not priced. Unknown provider cost is null, never assumed free."
        )
        result["environment"] = {
            "python": platform.python_version(),
            "cpu": platform.processor(),
            "logical_cpus": os.cpu_count(),
            "threads": cfg.THREADS,
            "system_ram_gb": round(psutil.virtual_memory().total / 1024**3, 2),
            "packages": {
                p: importlib.metadata.version(p)
                for p in [
                    "faster-whisper",
                    "ctranslate2",
                    "sherpa-onnx",
                    "httpx",
                    "onnx-asr",
                ]
            },
        }
        result["environment"]["pipeline_source_sha256"] = PIPELINE_SOURCE_HASH
        result["environment"]["source_hashes"] = {
            p.name: sha256(p) for p in Path(__file__).parent.glob("*.py")
        }
        model_id, model_path = cfg.STT_PROFILES[
            options.get("stt_profile", "bangla_asr")
        ]
        manifest = model_path / "manifest.json"
        if (
            not manifest.exists()
            and options.get("stt_profile", "bangla_asr") == "bangla_asr"
        ):
            manifest = cfg.MODELS / "manifest.json"
        result["models"] = (
            json.loads(manifest.read_text("utf-8"))
            if manifest.exists()
            else {"stt_id": model_id, "quantization": "int8"}
        )
        result["models"]["llm_configured_id"] = cfg.LLM_MODEL
        result["decoding"] = {
            "language": "bn",
            "task": "transcribe",
            "beam_size": 3,
            "without_timestamp_tokens": True,
            "word_alignment": "cross-attention DTW via faster-whisper",
            "vad_filter": True,
            "condition_on_previous_text": False,
        }
        if options.get("stt_profile") in ("zipformer", "indicconformer"):
            result["decoding"] = {
                "language": "bn",
                "engine": options["stt_profile"],
                "internal_chunk_cap_seconds": 15,
                "word_alignment": "acoustic token emission times; approximate 40ms word ends",
                "boundary": "minimum 40ms energy in last 2 seconds; no dropped samples",
                "live_streaming": False,
            }
        result["decoding"]["effective_cpu_threads"] = (
            cfg.THREADS
            if options.get("stt_profile") in ("zipformer", "indicconformer")
            else cfg.WHISPER_THREADS
        )
        result["stage"] = result["status"]
        atomic_json(output, result)
        update(result["status"], {})
    return result
