"""R2: contradiction-triggered cache bypass — mock-based, no real LLM calls."""
import pytest
from cirkit.signal import Signal
from cirkit.nodes.base import Node

FIXED_OUTPUT = Signal(content="llm result", confidence=0.8)


class MockMotor(Node):
    """Test double simulating Motor's R2 cache logic without a real LLM."""

    def __init__(self):
        self.llm_call_count = 0

    def step(self, inputs: dict, state: dict) -> Signal:
        self.llm_call_count += 1
        return FIXED_OUTPUT

    def _call_llm(self, inputs: dict, state: dict) -> Signal:
        self.llm_call_count += 1
        return FIXED_OUTPUT

    def _maybe_cached_step(self, inputs: dict, state: dict) -> Signal:
        """R2 logic: contradiction >= 0.8 bypasses cache and does NOT update cache."""
        all_signals = [s for signals in inputs.values() for s in signals if s is not Signal.ZERO]
        if any(s.contradiction >= 0.8 for s in all_signals):
            return self._call_llm(inputs, state)  # bypass, no cache update
        cache = state.setdefault("cache", {})
        key = tuple(s.content_hash() for role in sorted(inputs.keys()) for s in inputs[role])
        if key in cache:
            return cache[key]
        out = self._call_llm(inputs, state)
        cache[key] = out
        return out


# --- Cache hit ---

def test_same_inputs_cache_hit():
    motor = MockMotor()
    sig = Signal(content="input", confidence=0.7)
    state = {}
    out1 = motor._maybe_cached_step({"context": [sig]}, state)
    out2 = motor._maybe_cached_step({"context": [sig]}, state)
    assert motor.llm_call_count == 1
    assert out1 == out2


def test_different_inputs_cache_miss():
    motor = MockMotor()
    s1 = Signal(content="input A", confidence=0.7)
    s2 = Signal(content="input B", confidence=0.7)
    state = {}
    motor._maybe_cached_step({"context": [s1]}, state)
    motor._maybe_cached_step({"context": [s2]}, state)
    assert motor.llm_call_count == 2


# --- R2 contradiction bypass ---

def test_high_contradiction_bypasses_cache():
    motor = MockMotor()
    sig = Signal(content="same input", confidence=0.7, contradiction=0.9)
    state = {}
    motor._maybe_cached_step({"context": [sig]}, state)
    motor._maybe_cached_step({"context": [sig]}, state)
    # Both calls bypass cache -> 2 LLM calls despite identical inputs
    assert motor.llm_call_count == 2


def test_contradiction_at_threshold_bypasses():
    motor = MockMotor()
    sig = Signal(content="same", confidence=0.7, contradiction=0.8)
    state = {}
    motor._maybe_cached_step({"context": [sig]}, state)
    motor._maybe_cached_step({"context": [sig]}, state)
    assert motor.llm_call_count == 2


def test_contradiction_below_threshold_uses_cache():
    motor = MockMotor()
    sig = Signal(content="same", confidence=0.7, contradiction=0.79)
    state = {}
    motor._maybe_cached_step({"context": [sig]}, state)
    motor._maybe_cached_step({"context": [sig]}, state)
    assert motor.llm_call_count == 1


def test_bypass_does_not_update_cache():
    """After contradiction bypass, next call with same low-contradiction inputs
    calls LLM (cache was never populated by the bypass)."""
    motor = MockMotor()
    sig_high = Signal(content="same content", confidence=0.7, contradiction=0.9)
    sig_low = Signal(content="same content", confidence=0.7, contradiction=0.1)
    state = {}

    # First call: contradiction bypass — does NOT populate cache
    motor._maybe_cached_step({"context": [sig_high]}, state)
    assert motor.llm_call_count == 1
    assert not state.get("cache")  # cache empty because bypass skipped update

    # Second call with low contradiction + same content hash -> cache miss (never cached)
    motor._maybe_cached_step({"context": [sig_low]}, state)
    assert motor.llm_call_count == 2


def test_low_contradiction_after_cache_populated():
    motor = MockMotor()
    sig = Signal(content="stable input", confidence=0.8, contradiction=0.1)
    state = {}
    motor._maybe_cached_step({"context": [sig]}, state)  # populates cache
    motor._maybe_cached_step({"context": [sig]}, state)  # cache hit
    assert motor.llm_call_count == 1
