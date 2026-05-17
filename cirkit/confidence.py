import math
import re

HEDGE_PHRASES = [
    "actually",
    "wait",
    "let me reconsider",
    "on second thought",
    "i take it back",
    "correction",          # colon handled by word boundary; \bcorrection\b matches "correction:"
]

_CONF_RE = re.compile(r'\{"confidence":\s*(-?[0-9]*\.?[0-9]+)\}')

_HEDGE_RE = re.compile(
    r'\b(?:' + '|'.join(re.escape(p) for p in HEDGE_PHRASES) + r')\b',
    re.IGNORECASE,
)


def parse_confidence(raw_output: str) -> tuple[str, float]:
    """Parse Motor output into (content, confidence).

    1. fullmatch last non-empty line for {"confidence": X} — strip that line from content.
    2. Fallback if missing: clamp(0.5 + 0.4 * tanh((len-200)/400), 0.1, 0.9).
       Apply hedge cap (max 0.5) only on fallback path — explicit JSON overrides hedges.
    3. Word-boundary matching for hedges prevents false positives (await, factually, etc.).
    """
    if not raw_output or not raw_output.strip():
        return ("", 0.1)

    lines = raw_output.rstrip().splitlines()
    last_line = ""
    last_line_idx = len(lines)
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip():
            last_line = lines[i].strip()
            last_line_idx = i
            break

    content = raw_output
    confidence = None

    match = _CONF_RE.fullmatch(last_line)          # M8: full-line match only
    if match:
        confidence = max(0.0, min(1.0, float(match.group(1))))
        content = "\n".join(lines[:last_line_idx]).rstrip()

    if confidence is None:
        length = len(content)
        confidence = max(0.1, min(0.9, 0.5 + 0.4 * math.tanh((length - 200) / 400)))
        if _HEDGE_RE.search(content):              # I5: word-boundary, fallback path only
            confidence = min(confidence, 0.5)

    return (content, confidence)
