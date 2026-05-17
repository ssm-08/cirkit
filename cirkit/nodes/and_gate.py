from cirkit.nodes.base import Node
from cirkit.signal import Signal

_BLOCKED = Signal(
    content="[BLOCKED: insufficient confidence]",
    confidence=0.0,
    contradiction=1.0,
    urgency=0.0,
    relevance=0.0,
)


class AndGate(Node):
    """Multi-input consensus gate.

    Pass condition: ALL non-ZERO inputs have confidence >= cfg['threshold']
                    AND at least one non-ZERO input exists.

    If passing:
      - Merge content by cfg.get('merge_mode', 'concat'):
          concat    : join with '\\n---\\n', no LLM call
          dedupe    : line-level case-insensitive dedup, preserve first-occurrence order
          synthesize: same as concat + set flags['needs_synthesis']=True
      - metrics = per-channel MIN across all passing inputs
      - R4: if min_confidence >= cfg.get('early_exit_threshold', 0.9):
            set flags['consensus_locked']=True

    If blocked:
      Return Signal(content='[BLOCKED: insufficient confidence]',
                    confidence=0.0, contradiction=1.0, urgency=0.0, relevance=0.0)
      contradiction=1.0 triggers R2 cache invalidation in upstream Motors.

    If all inputs are Signal.ZERO: treat as blocked.
    """

    def __init__(self, config: dict):
        self.threshold = config["threshold"]
        self.early_exit_threshold = config.get("early_exit_threshold", 0.9)
        self.merge_mode = config.get("merge_mode", "concat")

    def step(self, inputs: dict, state: dict) -> Signal:
        # Collect all non-ZERO signals in role order: context, peer, feedback
        ordered: list[Signal] = []
        for role in ("context", "peer", "feedback"):
            ordered.extend(s for s in inputs.get(role, []) if s is not Signal.ZERO)

        # Also catch any other roles not in the standard set
        standard = {"context", "peer", "feedback"}
        for role in sorted(inputs.keys()):
            if role not in standard:
                ordered.extend(s for s in inputs[role] if s is not Signal.ZERO)

        if not ordered:
            return _BLOCKED

        if any(s.confidence < self.threshold for s in ordered):
            return _BLOCKED

        # Merge content
        if self.merge_mode == "dedupe":
            merged_content = _dedupe_lines(ordered)
        else:
            merged_content = "\n---\n".join(s.content for s in ordered)

        flags: dict = {}
        if self.merge_mode == "synthesize":
            flags["needs_synthesis"] = True

        min_confidence = min(s.confidence for s in ordered)
        min_contradiction = min(s.contradiction for s in ordered)
        min_urgency = min(s.urgency for s in ordered)
        min_relevance = min(s.relevance for s in ordered)

        if min_confidence >= self.early_exit_threshold:
            flags["consensus_locked"] = True

        return Signal(
            content=merged_content,
            confidence=min_confidence,
            contradiction=min_contradiction,
            urgency=min_urgency,
            relevance=min_relevance,
            flags=flags,
        )


def _dedupe_lines(signals: list[Signal]) -> str:
    seen: set[str] = set()
    result: list[str] = []
    for sig in signals:
        for line in sig.content.splitlines():
            key = line.strip().lower()
            if key not in seen:
                seen.add(key)
                result.append(line)
    return "\n".join(result)
