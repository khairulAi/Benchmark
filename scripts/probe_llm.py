"""Small synthetic Bengali integration probe; never prints credentials."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.llm import extract

ledger = []
utterances = [
    {
        "id": "u0001",
        "speaker": "speaker_00",
        "start": 0,
        "end": 2,
        "text": "কতদিন ধরে জ্বর হচ্ছে?",
        "role": "unknown",
    },
    {
        "id": "u0002",
        "speaker": "speaker_01",
        "start": 2,
        "end": 5,
        "text": "তিন দিন ধরে জ্বর হচ্ছে। কাশি নেই।",
        "role": "unknown",
    },
]
try:
    result, warnings = extract(utterances, ledger)
    print(
        json.dumps(
            {
                "status": "passed",
                "roles": result["roles"],
                "facts": result["facts"],
                "warnings": warnings,
                "ledger": ledger,
            },
            ensure_ascii=True,
        )
    )
except Exception as e:
    print(
        json.dumps(
            {"status": "failed", "error": str(e), "ledger": ledger}, ensure_ascii=True
        )
    )
    sys.exit(1)
