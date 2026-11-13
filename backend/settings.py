import os
from pathlib import Path
from urllib.parse import urlparse
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", encoding="utf-8-sig")
DATA = ROOT / "data"
MODELS = Path(os.getenv("MODELS_DIR", str(ROOT / "models")))
for folder in (DATA / "runs", DATA / "uploads", MODELS):
    folder.mkdir(parents=True, exist_ok=True)
LLM_BASE = os.getenv("LLM_BASE_URL", "").rstrip("/")
LLM_KEY, LLM_MODEL = os.getenv("LLM_API_KEY", ""), os.getenv("LLM_MODEL", "")
if LLM_BASE and (
    urlparse(LLM_BASE).scheme != "https"
    or urlparse(LLM_BASE).username
    or urlparse(LLM_BASE).password
):
    raise RuntimeError("LLM_BASE_URL must be HTTPS without embedded credentials")
STT_ID = "bangla-speech-processing/BanglaASR"
STT_PATH = MODELS / "bangla-asr-int8"
STT_PROFILES = {
    "bangla_asr": (STT_ID, STT_PATH),
    "vivasoft": ("vivasoft/whisper-small-bn", MODELS / "vivasoft-int8"),
}
STT_PROFILES.update(
    {
        "zipformer": (
            "SayedShaun/bangla-zipformer-onnx",
            MODELS / "bangla-zipformer-int8",
        ),
        "indicconformer": (
            "OpenVoiceOS/ai4bharat-indicconformer-bn-onnx",
            MODELS / "indicconformer-bn-int8",
        ),
    }
)
SEGMENTATION = MODELS / "sherpa-onnx-pyannote-segmentation-3-0" / "model.onnx"
EMBEDDING = MODELS / "3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx"
THREADS = max(1, min(int(os.getenv("CPU_THREADS", "4")), os.cpu_count() or 1))


def configured_price(name):
    value = os.getenv(name, "").strip()
    if not value:
        return None
    number = float(value)
    if number < 0:
        raise ValueError(f"{name} cannot be negative")
    return number


DEFAULT_STT_PROFILE = os.getenv("DEFAULT_STT_PROFILE", "zipformer")
if DEFAULT_STT_PROFILE not in STT_PROFILES:
    raise RuntimeError("Unknown DEFAULT_STT_PROFILE")

WHISPER_THREADS = max(1, min(int(os.getenv("WHISPER_CPU_THREADS", "2")), THREADS))

DENOISER = MODELS / "gtcrn_simple.onnx"
STREAMING_MODEL = MODELS / "vosk-small-streaming-bn-int8"
VOICE_THRESHOLD = float(os.getenv("VOICE_MATCH_THRESHOLD", "0.70"))
VOICE_MARGIN = float(os.getenv("VOICE_MATCH_MARGIN", "0.10"))
if not 0 < VOICE_THRESHOLD <= 1 or not 0 <= VOICE_MARGIN <= 1:
    raise RuntimeError("Invalid voice matching thresholds")
