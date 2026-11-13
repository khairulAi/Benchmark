"""Run the user-requested Hermes review in an isolated project directory."""

import json
import argparse
import os
import subprocess
import time
from pathlib import Path

from dotenv import dotenv_values


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    work = (
        root / "data" / ("hermes-features-review" if args.features else "hermes-review")
    )
    work.mkdir(parents=True, exist_ok=True)
    config = dotenv_values(root / ".env", encoding="utf-8-sig")
    instructions = (
        "Act as an independent Hermes code reviewer for a Bengali speech benchmark. "
        "Target Windows CPU and 8 GB RAM, often only 700 MB available. "
        "Review the supplied code only. Do not run tools, inspect other files or edit anything. "
        "Prioritize actual accuracy/resource/reproducibility defects and propose a maintainable "
        "STT adapter design. Existing Bengali Whisper small INT8 models have omissions. "
        "New candidates: SayedShaun/bangla-zipformer-onnx INT8 (65.5M, <=20-second inputs), "
        "OpenVoiceOS/ai4bharat-indicconformer-bn-onnx INT8. "
        "The user attests the first two minutes of the supplied script were verified, "
        "and authorizes choosing a complete nearby dialogue boundary. "
        "No model is established as best until an identically scoped reference comparison. "
        "Explain how to preserve original speaker timestamps with CTC/transducer tokens. "
        "Return concise prioritized findings with concrete fixes."
    )
    if args.features:
        instructions = (
            "Independent Hermes implementation review. This Windows/8GB CPU Bengali app now adds "
            "stateful Vosk PCM WebSocket drafts then separate final Zipformer analysis, GTCRN denoising, "
            "and local voice embeddings encrypted by Fernet with current-user DPAPI key wrapping. "
            "Review supplied source only, no tools or other files. Find concrete security, correctness, "
            "concurrency and resource-release bugs. Return exact suggested patches and meaningful test "
            "cases. Don't invent unsupported API options. The FastAPI app registers these routes; "
            "its shared lock serializes live/enrollment/batch inference. launch accepts reservation="
            "live-id and atomically replaces that active ID. Identity matching runs AFTER LLM extraction, "
            "so profile data and biometrics are never sent to the LLM. No accuracy claim is permitted "
            "without human reference. Focus on implementation, not generic disclaimers."
        )
    parts = [instructions]
    source_files = (
        [
            "backend/feature_routes.py",
            "backend/streaming.py",
            "backend/voices.py",
            "backend/enhancement.py",
        ]
        if args.features
        else [
            "backend/pipeline.py",
            "backend/settings.py",
            "backend/core.py",
            "backend/evaluation.py",
        ]
    )
    for name in source_files:
        parts.append(f"\nFILE {name}\n{(root / name).read_text('utf-8')}")
    query = work / "review-input.txt"
    query.write_text("\n".join(parts), encoding="utf-8")
    environment = os.environ.copy()
    environment.update(
        {
            "HERMES_HOME": str(
                Path(config.get("MODELS_DIR") or root / "models").resolve().parent
                / (
                    "hermes-features-review-home"
                    if args.features
                    else "hermes-benchmark-review-home"
                )
            ),
            "OPENAI_API_KEY": config["LLM_API_KEY"],
            "OPENAI_BASE_URL": config["LLM_BASE_URL"],
            "PYTHONIOENCODING": "utf-8",
        }
    )
    installations = Path(os.environ["LOCALAPPDATA"]) / "hermes" / "installs"
    executable = None
    for facts_path in installations.glob("*/facts.json"):
        facts = json.loads(facts_path.read_text("utf-8"))
        candidate = (
            Path(facts.get("packages", {}).get("venv", {}).get("environment", ""))
            / "Scripts/python.exe"
        )
        if candidate.is_file():
            executable = candidate
            break
    if executable is None:
        raise RuntimeError(
            "No committed Hermes runtime found; repair the Hermes installation first"
        )
    arguments = [
        str(executable),
        "-m",
        "hermes_cli.main",
        "chat",
        "--query-file",
        str(query),
        "--oneshot",
        "--quiet",
        "--provider",
        "custom",
        "--base-url",
        config["LLM_BASE_URL"],
        "--model",
        config["LLM_MODEL"],
        "--safe-mode",
        "--toolsets",
        "file",
        "--max-turns",
        "4",
        "--in",
        str(work),
    ]
    started = time.monotonic()
    process = subprocess.run(
        arguments,
        cwd=work,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=240,
    )
    secret = config["LLM_API_KEY"]
    output = process.stdout.replace(secret, "[REDACTED]")
    errors = process.stderr.replace(secret, "[REDACTED]")
    (work / "review.md").write_text(output, encoding="utf-8")
    (work / "stderr.txt").write_text(errors, encoding="utf-8")
    metadata = {
        "agent": "NousResearch Hermes Agent",
        "model": config["LLM_MODEL"],
        "returncode": process.returncode,
        "elapsed_seconds": round(time.monotonic() - started, 2),
        "output_characters": len(output),
    }
    (work / "invocation.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    print(json.dumps(metadata))
    if process.returncode:
        print(errors[-1500:])
        print(output[-1500:])
    raise SystemExit(process.returncode)


if __name__ == "__main__":
    main()
