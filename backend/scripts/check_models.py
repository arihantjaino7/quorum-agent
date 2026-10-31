"""List the Groq models this key can use and confirm the configured ones exist.

    cd backend && python -m scripts.check_models
"""

import sys

import httpx

from app.config import get_settings
from app.integrations.llm import GROQ_BASE, _api_key


def main() -> int:
    s = get_settings()
    try:
        r = httpx.get(f"{GROQ_BASE}/models", headers={"Authorization": f"Bearer {_api_key()}"}, timeout=10)
    except httpx.HTTPError as e:
        print(f"Groq unreachable: {e}")
        return 2
    if r.status_code != 200:
        print(f"Groq answered {r.status_code}: {r.text[:200]}")
        return 2
    ids = sorted(m["id"] for m in r.json()["data"] if m.get("active", True))
    print("Models available to this key:")
    for i in ids:
        print("  ", i)
    missing = 0
    for label, model in [("GROQ_MODEL_STRONG", s.groq_model_strong), ("GROQ_MODEL_FAST", s.groq_model_fast),
                         ("GROQ_MODEL_WHISPER", s.groq_model_whisper)]:
        ok = model in ids
        missing += not ok
        print(f"{'OK     ' if ok else 'MISSING'} {label} = {model}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
