"""Download public weights and convert Bengali Whisper to CPU INT8 (one-time)."""

import json
import argparse
import sys
import tarfile
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import settings as cfg
from backend.core import atomic_json, sha256


def download(url, target):
    if target.exists():
        return
    print("Downloading", target.name, flush=True)
    temp = target.with_suffix(target.suffix + ".download")
    urllib.request.urlretrieve(url, temp)
    temp.replace(target)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--profile", choices=cfg.STT_PROFILES, default=cfg.DEFAULT_STT_PROFILE
    )
    args = parser.parse_args()
    model_id, model_path = cfg.STT_PROFILES[args.profile]
    from huggingface_hub import model_info, snapshot_download

    from backend.stt import model_ready

    ready = model_ready(args.profile, model_path)
    manifest_path = model_path / "manifest.json"
    previous = (
        json.loads(manifest_path.read_text("utf-8")) if manifest_path.exists() else {}
    )
    revision = previous.get("revision") if ready else model_info(model_id).sha
    if not ready and args.profile in ("zipformer", "indicconformer"):
        patterns = (
            ["int8/*", "tokens.txt", "README.md", "LICENSE"]
            if args.profile == "zipformer"
            else ["model.int8.onnx", "config.json", "vocab.txt", "README.md", "LICENSE"]
        )
        snapshot_download(
            model_id, revision=revision, allow_patterns=patterns, local_dir=model_path
        )
    elif not ready and args.profile not in ("zipformer", "indicconformer"):
        from ctranslate2.converters import TransformersConverter

        source = snapshot_download(
            model_id,
            revision=revision,
            allow_patterns=["*.json", "*.txt", "*.safetensors"],
            local_dir=cfg.MODELS / (args.profile + "-source"),
        )
        # This checkpoint publishes vocab/merges but no tokenizer.json. Build its
        # own fast tokenizer; do not silently substitute another model's vocab.
        from transformers import AutoTokenizer

        AutoTokenizer.from_pretrained(source, use_fast=True).save_pretrained(source)
        TransformersConverter(
            source,
            copy_files=["tokenizer.json", "preprocessor_config.json"],
            load_as_float16=True,
            low_cpu_mem_usage=True,
        ).convert(str(model_path), quantization="int8", force=True)
    url = "https://github.com/k2-fsa/sherpa-onnx/releases/download/"
    archive = cfg.MODELS / "segmentation.tar.bz2"
    if not cfg.SEGMENTATION.exists():
        download(
            url
            + "speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2",
            archive,
        )
        with tarfile.open(archive) as tar:
            tar.extractall(cfg.MODELS, filter="data")
    download(url + "speaker-recongition-models/" + cfg.EMBEDDING.name, cfg.EMBEDDING)
    from backend.stt import model_files

    manifest = {
        "stt_id": model_id,
        "revision": revision,
        "quantization": "int8",
        "segmentation_source": url + "speaker-segmentation-models",
        "embedding_source": url + "speaker-recongition-models",
        "hashes": {
            str(p.relative_to(cfg.MODELS)): sha256(p)
            for p in model_files(args.profile, model_path)
            + [cfg.SEGMENTATION, cfg.EMBEDDING]
        },
    }
    atomic_json(model_path / "manifest.json", manifest)
    if args.profile == "bangla_asr":
        atomic_json(cfg.MODELS / "manifest.json", manifest)
    print("All models ready. Manifest:", model_path / "manifest.json", flush=True)


if __name__ == "__main__":
    main()
