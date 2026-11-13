from __future__ import annotations
import hashlib
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
import os
import tempfile
import time
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Role(StrictModel):
    speaker: str
    role: Literal["doctor", "patient", "unknown"]
    evidence_ids: list[str]


class Fact(StrictModel):
    category: Literal[
        "symptom",
        "duration",
        "history",
        "medication",
        "allergy",
        "vital",
        "test",
        "advice",
        "assessment",
        "follow_up",
        "demographic",
    ]
    value: str = Field(min_length=1, max_length=2000)
    polarity: Literal["present", "absent", "uncertain"]
    evidence_id: str
    quote: str = Field(min_length=1, max_length=2000)


class Extraction(StrictModel):
    roles: list[Role]
    facts: list[Fact]
    summary_bn: str
    warnings: list[str]


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text).translate(
        str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
    )
    return " ".join(
        "".join(" " if unicodedata.category(c)[0] in "PS" else c for c in text)
        .lower()
        .split()
    )


def edit_counts(reference: list, hypothesis: list) -> dict:
    previous = [(j, 0, 0, j) for j in range(len(hypothesis) + 1)]
    for i, ref in enumerate(reference, 1):
        row = [(i, 0, i, 0)]
        for j, hyp in enumerate(hypothesis, 1):
            if ref == hyp:
                row.append(previous[j - 1])
            else:
                cost, s, d, ins = previous[j - 1]
                sub = (cost + 1, s + 1, d, ins)
                cost, s, d, ins = previous[j]
                delete = (cost + 1, s, d + 1, ins)
                cost, s, d, ins = row[j - 1]
                insert = (cost + 1, s, d, ins + 1)
                row.append(min((sub, delete, insert), key=lambda x: x[0]))
        previous = row
    errors, substitutions, deletions, insertions = previous[-1]
    return {
        "rate": errors / len(reference) if reference else None,
        "reference_units": len(reference),
        "substitutions": substitutions,
        "deletions": deletions,
        "insertions": insertions,
    }


def transcript_metrics(reference: str, hypothesis: str) -> dict:
    r, h = normalize(reference), normalize(hypothesis)
    return {
        "wer": edit_counts(r.split(), h.split()),
        "cer": edit_counts(list(r.replace(" ", "")), list(h.replace(" ", ""))),
        "normalization": "NFC, lowercase, Bengali digits to ASCII, punctuation/symbols to spaces. CER excludes whitespace. No spelling correction.",
    }


def docx_script(path: Path) -> list[dict]:
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    utterances = []
    for paragraph in root.findall(".//w:p", ns):
        text = "".join(t.text or "" for t in paragraph.findall(".//w:t", ns)).strip()
        if not text:
            continue
        match = re.match(r"^(Doctor|Patient)\s*:\s*(.*)", text, re.I)
        if match:
            utterances.append(
                {
                    "id": f"ref_{len(utterances) + 1:03d}",
                    "role": match[1].lower(),
                    "text": match[2],
                }
            )
        elif utterances:
            utterances[-1]["text"] += "\n" + text
    return utterances


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, value: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False
    ) as handle:
        handle.write(payload)
        temp = Path(handle.name)
    try:
        for attempt in range(5):
            try:
                os.replace(temp, path)
                break
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.02)
    finally:
        temp.unlink(missing_ok=True)


def bind_words(segments: list[dict], speakers: list[dict]) -> list[dict]:
    output = []
    for segment in segments:
        for word in segment.get("words") or [
            {"start": segment["start"], "end": segment["end"], "word": segment["text"]}
        ]:
            start, end = word["start"], word["end"]
            scores = {}
            for turn in speakers:
                overlap = max(0, min(end, turn["end"]) - max(start, turn["start"]))
                scores[turn["speaker"]] = scores.get(turn["speaker"], 0) + overlap
            ranked = sorted(scores.items(), key=lambda p: p[1], reverse=True)
            chosen = ranked[0][0] if ranked and ranked[0][1] > 0 else "unknown"
            if (
                len(ranked) > 1
                and ranked[1][1] > 0
                and ranked[1][1] >= ranked[0][1] * 0.7
            ):
                chosen = "unknown"
            if (
                output
                and output[-1]["speaker"] == chosen
                and start - output[-1]["end"] < 1.5
            ):
                output[-1]["end"] = end
                output[-1]["text"] += word["word"]
            else:
                output.append(
                    {
                        "id": f"u{len(output) + 1:04d}",
                        "speaker": chosen,
                        "start": start,
                        "end": end,
                        "text": word["word"].lstrip(),
                        "role": "unknown",
                    }
                )
    return output


def validate_evidence(
    extraction: Extraction, utterances: list[dict]
) -> tuple[dict, list[str]]:
    lookup = {u["id"]: u for u in utterances}
    speakers = {u["speaker"] for u in utterances}
    result = extraction.model_dump()
    warnings, roles, seen = [], [], set()
    for role in result["roles"]:
        if role["speaker"] in seen or role["speaker"] not in speakers:
            warnings.append("Dropped duplicate/unknown speaker role")
            continue
        seen.add(role["speaker"])
        valid_ids = list(
            dict.fromkeys(
                i
                for i in role["evidence_ids"]
                if i in lookup and lookup[i]["speaker"] == role["speaker"]
            )
        )
        if len(valid_ids) != len(role["evidence_ids"]):
            warnings.append("Discarded invalid role evidence IDs")
        role["evidence_ids"] = valid_ids
        if role["speaker"] == "unknown" or (
            role["role"] != "unknown" and not valid_ids
        ):
            role["role"] = "unknown"
            warnings.append("No valid role evidence; marked unknown")
        roles.append(role)
    result["roles"] = roles
    facts = []
    for fact in result["facts"]:
        evidence = lookup.get(fact["evidence_id"])
        if (
            not evidence
            or not normalize(fact["quote"])
            or normalize(fact["quote"]) not in normalize(evidence["text"])
        ):
            warnings.append("Dropped fact with missing/non-matching evidence quote")
            continue
        facts.append(fact)
    result["facts"] = facts
    return result, warnings
