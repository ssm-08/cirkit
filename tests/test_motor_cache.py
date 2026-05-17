"""R2: contradiction-triggered cache bypass — mock-based, no real LLM calls."""
import pytest
from unittest.mock import patch
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


# --- C1: Signal.ZERO filtering ---


def test_c1_zero_in_inputs_does_not_cause_cache_miss():
    """C1: Signal.ZERO in inputs must be filtered from cache key.

    Call 1: inputs = {"context": [real_sig, Signal.ZERO]}
    Call 2: inputs = {"context": [real_sig]}
    Same effective content -> should be a cache HIT (only 1 LLM call).
    """
    real_sig = Signal(content="hello", confidence=0.7)
    call_count = [0]

    def fake_llm(prompt, timeout=60):
        call_count[0] += 1
        return 'result\n{"confidence": 0.8}'

    with patch("cirkit.llm.call_claude", fake_llm):
        from cirkit.nodes.motor import Motor
        m = Motor({"system": "test"})
        state = {}
        m._maybe_cached_step({"context": [real_sig, Signal.ZERO]}, state)
        m._maybe_cached_step({"context": [real_sig]}, state)
        assert call_count[0] == 1, "Expected cache hit but got cache miss"


def test_i2_motor_cache_bounded_at_64():
    """I2: Motor cache must never exceed 64 entries."""
    call_count = [0]

    def fake_llm(prompt, timeout=60):
        call_count[0] += 1
        return f'result {call_count[0]}\n{{"confidence": 0.8}}'

    with patch("cirkit.llm.call_claude", fake_llm):
        from cirkit.nodes.motor import Motor
        m = Motor({"system": "test"})
        state = {}
        # Feed 100 unique signals
        for i in range(100):
            sig = Signal(content=f"unique input {i}", confidence=0.7)
            m._maybe_cached_step({"context": [sig]}, state)
        assert len(state["cache"]) <= 64


def test_i2_lru_eviction_oldest_entry():
    """I2: When cache is full, oldest (LRU) entry is evicted."""
    call_count = [0]

    def fake_llm(prompt, timeout=60):
        call_count[0] += 1
        return f'out {call_count[0]}\n{{"confidence": 0.8}}'

    with patch("cirkit.llm.call_claude", fake_llm):
        from cirkit.nodes.motor import Motor
        m = Motor({"system": "test"})
        state = {}
        # Fill cache to 64
        sigs = [Signal(content=f"sig {i}", confidence=0.7) for i in range(64)]
        for sig in sigs:
            m._maybe_cached_step({"context": [sig]}, state)
        initial_calls = call_count[0]
        # Add one more — evicts oldest (sigs[0])
        new_sig = Signal(content="sig 64", confidence=0.7)
        m._maybe_cached_step({"context": [new_sig]}, state)
        assert len(state["cache"]) == 64
        # Accessing sigs[0] again should be a cache miss (evicted)
        m._maybe_cached_step({"context": [sigs[0]]}, state)
        assert call_count[0] == initial_calls + 2  # new_sig miss + sigs[0] re-miss
