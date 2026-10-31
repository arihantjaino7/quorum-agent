"""Quote verification: every source_quote must be words that were actually said.

``snap(quote, source)`` returns (quote, changed). A quote found verbatim (ignoring case and spacing)
comes back as the exact span from the source. Otherwise it is replaced by the closest sentence of the
source, so citations are always real.
"""

import difflib
import re

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")


def sentences(source: str) -> list[str]:
    out = []
    for line in _SENTENCE_END.split(source):
        line = line.strip()
        # Transcript lines ("Priya: ...") keep their speaker label out of the quote.
        line = re.sub(r"^[A-Z][\w .'-]{0,40}:\s+", "", line)
        if line:
            out.append(line)
    return out


def find_verbatim(quote: str, source: str) -> str | None:
    words = quote.split()
    if not words:
        return None
    pattern = r"\s+".join(re.escape(w) for w in words)
    m = re.search(pattern, source, re.I)
    return m.group(0) if m else None


def snap(quote: str, source: str) -> tuple[str, bool]:
    exact = find_verbatim(quote.strip().strip('"“”'), source)
    if exact is not None:
        return exact, exact != quote
    candidates = sentences(source)
    if not candidates:
        return quote, False
    q = quote.lower()
    best = max(candidates, key=lambda s: difflib.SequenceMatcher(None, q, s.lower()).ratio())
    return best, True
