"""Prepare small CPU streaming/denoising assets, with pinned model revision."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import settings as cfg
from backend.core import atomic_json, sha256
from scripts.prepare_models import download


def main():
    from huggingface_hub import snapshot_download

    revision = "19d0fc5890941faab7b080a26b6821f3d456fbf1"
    names = ["encoder.int8.onnx", "decoder.onnx", "joiner.int8.onnx", "tokens.txt"]
    if not all((cfg.STREAMING_MODEL / name).is_file() for name in names):
        snapshot_download(
            "bbbipul/vosk-small-streaming-bn-int8",
            revision=revision,
            allow_patterns=names + ["README.md", "LICENSE"],
            local_dir=cfg.STREAMING_MODEL,
        )
    url = "https://github.com/k2-fsa/sherpa-onnx/releases/download/speech-enhancement-models/gtcrn_simple.onnx"
    download(url, cfg.DENOISER)
    atomic_json(
        cfg.MODELS / "feature-manifest.json",
        {
            "streaming": {
                "id": "bbbipul/vosk-small-streaming-bn-int8",
                "revision": revision,
                "quantization": "int8",
                "hashes": {name: sha256(cfg.STREAMING_MODEL / name) for name in names},
            },
            "denoiser": {"id": "GTCRN", "source": url, "sha256": sha256(cfg.DENOISER)},
            "embedding_sha256": sha256(cfg.EMBEDDING),
        },
    )
    print(
        "Streaming, denoising and speaker assets ready; feature-manifest.json written"
    )


if __name__ == "__main__":
    main()
