import numpy as np
from scipy.optimize import linear_sum_assignment
from .core import normalize, transcript_metrics


def score(result, reference):
    if not reference["verified"]:
        return {
            "status": "unverified",
            "message": "No accuracy claimed until a human verifies the transcript against this exact audio clip.",
        }
    hypothesis = " ".join(s["text"] for s in result.get("asr_segments", []))
    report = {
        "status": "human_reference",
        "transcription": transcript_metrics(reference["transcript"], hypothesis),
        "der": None,
        "role_accuracy": None,
        "fact_f1": None,
    }
    if reference.get("facts") is not None:

        def key(f):
            return (f["category"], normalize(f["value"]), f["polarity"])

        expected = {key(f) for f in reference["facts"]}
        actual = {key(f) for f in (result.get("extraction") or {}).get("facts", [])}
        tp = len(expected & actual)
        precision = tp / len(actual) if actual else (1.0 if not expected else 0.0)
        recall = tp / len(expected) if expected else (1.0 if not actual else 0.0)
        report["fact_f1"] = {
            "precision": precision,
            "recall": recall,
            "f1": 2 * precision * recall / (precision + recall)
            if precision + recall
            else 0,
            "matched": tp,
            "expected": len(expected),
            "predicted": len(actual),
            "method": "Exact normalized category/value/polarity set match; no LLM judge or synonym matching.",
        }
    turns = reference.get("speaker_segments")
    if turns:
        duration = result["audio"]["analyzed_seconds"]
        step = 0.01
        centers = np.arange(step / 2, duration, step)
        ref_names = sorted({s["speaker"] for s in turns})
        pred_names = sorted({s["speaker"] for s in result.get("speaker_segments", [])})
        ref = np.full(len(centers), -1, dtype=int)
        pred = np.full(len(centers), -1, dtype=int)
        overlap = np.zeros(len(centers), dtype=int)
        for s in turns:
            mask = (centers >= s["start"]) & (centers < s["end"])
            overlap[mask] += 1
            ref[mask] = ref_names.index(s["speaker"])
        for s in result.get("speaker_segments", []):
            pred[(centers >= s["start"]) & (centers < s["end"])] = pred_names.index(
                s["speaker"]
            )
        valid = overlap < 2
        matrix = np.zeros((len(ref_names), len(pred_names)), dtype=int)
        for i in range(len(ref_names)):
            for j in range(len(pred_names)):
                matrix[i, j] = np.sum(valid & (ref == i) & (pred == j))
        rows, cols = linear_sum_assignment(-matrix)
        mapping = dict(zip(cols, rows))
        mapped = np.array([mapping.get(p, -2) if p >= 0 else -1 for p in pred])
        speech = valid & (ref >= 0)
        joint = speech & (pred >= 0)
        misses = int(np.sum(speech & (pred < 0)))
        false = int(np.sum(valid & (ref < 0) & (pred >= 0)))
        confused = int(np.sum(joint & (mapped != ref)))
        total = int(np.sum(speech))
        report["der"] = {
            "rate": (misses + false + confused) / total if total else None,
            "miss_seconds": misses * step,
            "false_alarm_seconds": false * step,
            "confusion_seconds": confused * step,
            "reference_speech_seconds": total * step,
            "method": "10 ms frames, optimal speaker permutation, zero collar, overlapping reference speech excluded; not directly comparable to collar-based published DER.",
        }
        roles_ref = np.full(len(centers), "unknown", dtype=object)
        roles_pred = roles_ref.copy()
        for s in turns:
            roles_ref[(centers >= s["start"]) & (centers < s["end"])] = s.get(
                "role", "unknown"
            )
        for s in result.get("transcript", []):
            roles_pred[(centers >= s["start"]) & (centers < s["end"])] = s.get(
                "role", "unknown"
            )
        eligible = speech & (roles_ref != "unknown")
        if np.any(eligible):
            report["role_accuracy"] = {
                "rate": float(np.mean(roles_ref[eligible] == roles_pred[eligible])),
                "method": "Time-weighted doctor/patient role accuracy on non-overlap reference speech; unknown predictions count as wrong.",
            }
    return report
