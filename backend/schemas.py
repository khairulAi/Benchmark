"""Validated API request schemas."""

from __future__ import annotations
from pydantic import Field, model_validator
from . import settings as cfg
from .core import StrictModel


class Options(StrictModel):
    denoise: bool = False
    identify_voices: bool = False
    stt_profile: str = Field(
        default=cfg.DEFAULT_STT_PROFILE,
        pattern="^(bangla_asr|vivasoft|zipformer|indicconformer)$",
    )
    offset_seconds: float = Field(default=0, ge=0, le=7200)
    max_seconds: int = Field(default=120, ge=0, le=1200)
    num_speakers: int = Field(default=2, ge=1, le=6)
    strategy: str = Field(default="batch", pattern="^(batch|chunks)$")
    chunk_seconds: int = Field(default=30, ge=10, le=120)
    noise_snr_db: float | None = Field(default=None, ge=-5, le=40)
    use_llm: bool = True
    remote_permission: bool = False

    @model_validator(mode="after")
    def permission(self):
        if self.use_llm and not self.remote_permission:
            raise ValueError(
                "Confirm permission to send transcript to the configured LLM provider"
            )
        return self


class TimedReference(StrictModel):
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    speaker: str = Field(min_length=1, max_length=100)
    role: str = Field(default="unknown", pattern="^(doctor|patient|unknown)$")

    @model_validator(mode="after")
    def ordered(self):
        if self.end <= self.start:
            raise ValueError("end must exceed start")
        return self


class ExpectedFact(StrictModel):
    category: str
    value: str = Field(min_length=1)
    polarity: str = Field(pattern="^(present|absent|uncertain)$")


class Reference(StrictModel):
    transcript: str = Field(max_length=200000)
    verified: bool = False
    verification_note: str = Field(default="", max_length=2000)
    speaker_segments: list[TimedReference] | None = None
    facts: list[ExpectedFact] | None = None

    @model_validator(mode="after")
    def valid(self):
        if self.verified and not self.transcript.strip():
            raise ValueError("Verified transcript cannot be empty")
        return self


class ExtractionPermission(StrictModel):
    remote_permission: bool
