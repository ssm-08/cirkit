import sys
from collections import OrderedDict
from cirkit.nodes.base import Node
from cirkit.signal import Signal
from cirkit import llm, confidence

MOTOR_PREFIX = """You are a node in a reasoning circuit. You will be called multiple times.
The circuit handles correction via feedback — you do not need to be perfect this pass.

RULES (strict):
1. SINGLE PASS. Do not revise mid-response. Do not write "actually", "wait",
   "let me reconsider", or revise earlier sentences. Commit and move on.
2. If feedback from a previous iteration is present, address it directly.
3. If unsure, give your best answer and set confidence LOW. The loop will re-run you.
4. Final line MUST be exactly: {"confidence": 0.X}
   Where X is your belief, 0.0-1.0, that this signal should ADVANCE through the
   circuit (i.e. your output is correct and complete enough to proceed).
   - 0.9+ : very sure, advance
   - 0.5  : uncertain, may need another pass
   - 0.2- : likely wrong, expect rejection
5. Polarity convention: HIGH confidence = "this is good, send it forward."
   Never invert this. If your job is to detect badness (e.g., bug-finder),
   report 1 - badness_probability.

YOUR TASK:
"""


class Motor(Node):
    """LLM-backed reasoning node.

    R1: Role-grouped prompt assembly — [CONTEXT] / [PEER OUTPUTS] / [FEEDBACK FROM PREVIOUS ITERATION]
    R2: Cache bypass when any FEEDBACK input has contradiction >= 0.8 (upstream rejection only)
    R3: MOTOR_PREFIX always prepended to user system config — never overridable
    R6: confidence.parse_confidence handles hedge-phrase cap
    On LLMError: logs to stderr, returns Signal.ZERO (never raises)
    """

    def __init__(self, config: dict):
        self.config = config

    def _build_prompt(self, inputs: dict) -> str:
        parts = [f"{MOTOR_PREFIX}{self.config.get('system', '')}"]

        context_sigs = [s for s in inputs.get("context", []) if s is not Signal.ZERO and s.content]
        if context_sigs:
            parts.append("\n[CONTEXT]")
            parts.append("\n".join(s.content for s in context_sigs))

        peer_sigs = [s for s in inputs.get("peer", []) if s is not Signal.ZERO and s.content]
        if peer_sigs:
            parts.append("\n[PEER OUTPUTS]")
            if len(peer_sigs) == 1:
                parts.append(peer_sigs[0].content)
            else:
                for i, s in enumerate(peer_sigs, 1):
                    parts.append(f"PEER {i}: {s.content}")

        feedback_sigs = [s for s in inputs.get("feedback", []) if s is not Signal.ZERO and s.content]
        if feedback_sigs:
            parts.append("\n[FEEDBACK FROM PREVIOUS ITERATION]")
            parts.append("\n".join(s.content for s in feedback_sigs))

        return "\n".join(parts)

    def _call_llm(self, inputs: dict, state: dict) -> Signal:
        prompt = self._build_prompt(inputs)
        try:
            raw = llm.call_claude(prompt)
        except llm.LLMError as e:
            print(f"[Motor LLMError] {e}", file=sys.stderr)
            return Signal.ZERO
        content, conf = confidence.parse_confidence(raw)
        return Signal(content=content, confidence=conf)

    def _maybe_cached_step(self, inputs: dict, state: dict) -> Signal:
        if any(s.contradiction >= 0.8 for s in inputs.get("feedback", []) if s is not Signal.ZERO):
            return self._call_llm(inputs, state)
        cache = state.setdefault("cache", OrderedDict())
        key = tuple(
            s.content_hash()
            for role in sorted(inputs.keys())
            for s in inputs[role]
            if s is not Signal.ZERO          # C1: filter sentinels from key
        )
        if key in cache:
            cache.move_to_end(key)           # LRU: mark as recently used
            return cache[key]
        out = self._call_llm(inputs, state)
        cache[key] = out
        if len(cache) > 64:                  # I2: evict oldest entry
            cache.popitem(last=False)
        return out

    def step(self, inputs: dict, state: dict) -> Signal:
        return self._call_llm(inputs, state)
