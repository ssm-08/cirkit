import sys
from collections import OrderedDict
from cirkit.nodes.base import Node
from cirkit.signal import Signal
from cirkit import llm, confidence

_DELTA_LABELS = {"context": "CONTEXT", "peer": "PEER OUTPUTS", "feedback": "FEEDBACK"}

MOTOR_PREFIX = """You are a node in a reasoning circuit called multiple times.
RULES:
1. SINGLE PASS. No mid-response revisions. Commit and move on.
2. Address feedback from previous iterations directly.
3. If unsure, give best answer and set confidence LOW.
4. Confidence polarity: HIGH = output is good and should advance. Never invert.
5. Final line MUST be exactly: {"confidence": 0.X}  (0.0=wrong, 0.9+=sure)

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
        self.model: str | None = config.get("model")

    def _build_prompt(self, inputs: dict) -> tuple[str, dict[str, str]]:
        """Returns (full_prompt, sections) where sections is a snapshot of each role's content."""
        system = self.config.get("system", "")
        parts = [f"{MOTOR_PREFIX}{system}"]
        sections: dict[str, str] = {"system": system}

        context_sigs = [s for s in inputs.get("context", []) if s is not Signal.ZERO and s.content]
        ctx_text = "\n".join(s.content for s in context_sigs)
        sections["context"] = ctx_text
        if ctx_text:
            parts.append("\n[CONTEXT]")
            parts.append(ctx_text)

        peer_sigs = [s for s in inputs.get("peer", []) if s is not Signal.ZERO and s.content]
        if len(peer_sigs) == 1:
            peer_text = peer_sigs[0].content
        else:
            peer_text = "\n".join(f"PEER {i}: {s.content}" for i, s in enumerate(peer_sigs, 1))
        sections["peer"] = peer_text
        if peer_text:
            parts.append("\n[PEER OUTPUTS]")
            parts.append(peer_text)

        feedback_sigs = [s for s in inputs.get("feedback", []) if s is not Signal.ZERO and s.content]
        fb_text = "\n".join(s.content for s in feedback_sigs)
        sections["feedback"] = fb_text
        if fb_text:
            parts.append("\n[FEEDBACK FROM PREVIOUS ITERATION]")
            parts.append(fb_text)

        return "\n".join(parts), sections

    def _build_delta_prompt(self, curr: dict[str, str], prior: dict[str, str]) -> str | None:
        """Returns delta prompt for changed sections, or None if nothing changed (cache should prevent this)."""
        changed = {k for k in curr if curr[k] != prior.get(k, "")}
        if not changed:
            return None
        lines = ["UPDATE — your prior context changed. Refine your prior response accordingly.\n"]
        # system changes require full re-prompt (rare; fall back to caller)
        if "system" in changed:
            return None
        for section in ("context", "peer", "feedback"):
            if section in changed and curr[section]:
                label = _DELTA_LABELS[section]
                lines.append(f"[UPDATED {label}]")
                lines.append(curr[section])
        lines.append(
            '\n(MOTOR_PREFIX rules and system prompt still apply from this session.)'
            '\nFinal line MUST be: {"confidence": 0.X}'
        )
        return "\n".join(lines)

    def _call_llm(self, inputs: dict, state: dict) -> Signal:
        full_prompt, curr_sections = self._build_prompt(inputs)

        # Empty-input guard: if no non-zero content in any role, skip LLM call
        if not any(curr_sections[k] for k in ("context", "peer", "feedback")):
            return Signal.ZERO

        session_id: str | None = state.get("session_id")
        prior_sections: dict | None = state.get("last_sections")

        is_resume = prior_sections is not None and bool(session_id)
        used_delta = False
        prompt = full_prompt
        if is_resume:
            delta = self._build_delta_prompt(curr_sections, prior_sections)
            if delta is not None:
                prompt = delta
                used_delta = True

        try:
            result = llm.call_claude(prompt, session_id=session_id, resume=is_resume, model=self.model)
        except llm.LLMError as e:
            if used_delta:
                # Fail-soft: retry with full prompt if delta send failed
                print(f"[Motor LLMError delta] {e} — retrying with full prompt", file=sys.stderr)
                try:
                    result = llm.call_claude(full_prompt, session_id=session_id, resume=is_resume, model=self.model)
                    used_delta = False
                except llm.LLMError as e2:
                    print(f"[Motor LLMError] {e2}", file=sys.stderr)
                    return Signal.ZERO
            else:
                print(f"[Motor LLMError] {e}", file=sys.stderr)
                return Signal.ZERO

        state["last_sections"] = curr_sections

        usage_entry = {
            "tokens_in": result.tokens_in,
            "tokens_out": result.tokens_out,
            "cost_usd": result.cost_usd,
            "delta": used_delta,
        }
        state.setdefault("token_usage", []).append(usage_entry)

        content, conf = confidence.parse_confidence(result.content)
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
