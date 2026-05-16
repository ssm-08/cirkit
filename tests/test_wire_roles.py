"""R1: role-based input grouping and _maybe_cached_step caching."""
import pytest
from cirkit.signal import Signal
from cirkit.nodes.base import Node


class RecordingNode(Node):
    """Mock node that records calls and returns a fixed signal."""

    def __init__(self):
        self.call_count = 0
        self.last_inputs = None

    def step(self, inputs: dict, state: dict) -> Signal:
        self.call_count += 1
        self.last_inputs = inputs
        return Signal(content="recorded", confidence=0.7)


def test_step_receives_role_grouped_inputs():
    node = RecordingNode()
    s1 = Signal(content="ctx signal", confidence=0.8)
    s2 = Signal(content="fb signal", confidence=0.6)
    s3 = Signal(content="peer signal", confidence=0.7)
    state = {}
    node._maybe_cached_step(
        {"context": [s1], "feedback": [s2], "peer": [s3]},
        state,
    )
    assert node.call_count == 1
    assert node.last_inputs["context"] == [s1]
    assert node.last_inputs["feedback"] == [s2]
    assert node.last_inputs["peer"] == [s3]


def test_same_inputs_cache_hit():
    node = RecordingNode()
    s1 = Signal(content="x", confidence=0.8)
    inputs = {"context": [s1]}
    state = {}
    out1 = node._maybe_cached_step(inputs, state)
    out2 = node._maybe_cached_step(inputs, state)
    assert node.call_count == 1
    assert out1 == out2


def test_different_inputs_cache_miss():
    node = RecordingNode()
    s1 = Signal(content="x", confidence=0.8)
    s2 = Signal(content="y", confidence=0.8)
    state = {}
    node._maybe_cached_step({"context": [s1]}, state)
    node._maybe_cached_step({"context": [s2]}, state)
    assert node.call_count == 2


def test_cache_key_role_order_independent():
    """{"peer": [a], "context": [b]} same cache key as {"context": [b], "peer": [a]}."""
    node = RecordingNode()
    a = Signal(content="peer content", confidence=0.7)
    b = Signal(content="ctx content", confidence=0.9)
    state = {}

    node._maybe_cached_step({"context": [b], "peer": [a]}, state)
    assert node.call_count == 1

    # Same signals, different dict insertion order — should cache hit
    node._maybe_cached_step({"peer": [a], "context": [b]}, state)
    assert node.call_count == 1


def test_empty_inputs_cache():
    node = RecordingNode()
    state = {}
    out1 = node._maybe_cached_step({}, state)
    out2 = node._maybe_cached_step({}, state)
    assert node.call_count == 1
    assert out1 == out2
