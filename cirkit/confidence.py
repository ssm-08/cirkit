import math
import re

HEDGE_PHRASES = [
    "actually",
    "wait",
    "let me reconsider",
    "on second thought",
    "i take it back",
    "correction:",
]

_CONF_RE = re.compile(r'\{"confidence":\s*([0-9]*\.?[0-9]+)\}')


def parse_confidence(raw_output: str) -> tuple[str, float]:
    """Parse Motor output into (content, confidence).

    1. Regex on last non-empty line for {"confidence": X} — strip that line from content.
    2. Fallback if missing: clamp(0.5 + 0.4 * tanh((len-200)/400), 0.1, 0.9)
    3. R6: if any HEDGE_PHRASE found in content.lower(), cap confidence at 0.5.

    Never crashes on empty input — returns ("", 0.1) for empty string.
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

    match = _CONF_RE.search(last_line)
    if match:
        confidence = max(0.0, min(1.0, float(match.group(1))))
        content = "\n".join(lines[:last_line_idx]).rstrip()

    if confidence is None:
        length = len(content)
        confidence = max(0.1, min(0.9, 0.5 + 0.4 * math.tanh((length - 200) / 400)))

    if any(phrase in content.lower() for phrase in HEDGE_PHRASES):
        confidence = min(confidence, 0.5)

    return (content, confidence)
