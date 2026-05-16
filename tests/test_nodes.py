import pytest
from cirkit.signal import Signal
from cirkit.nodes.battery import Battery
from cirkit.nodes.sink import Sink
from cirkit.nodes.resistor import Resistor
from cirkit.nodes.and_gate import AndGate


# --- Battery ---

def test_battery_emits_content_and_user_prompt():
    b = Battery({"content": "base content", "accumulate": False})
    state = {"user_prompt": "user question"}
    out = b.step({}, state)
    assert out.content == "base content\nuser question"
    assert out.confidence == 1.0


def test_battery_missing_user_prompt():
    b = Battery({"content": "base", "accumulate": False})
    out = b.step({}, {})
    assert out.content == "base\n"
    assert out.confidence == 1.0


def test_battery_accumulate_appends_feedback():
    b = Battery({"content": "seed", "accumulate": True})
    state = {"user_prompt": "Q"}
    fb = Signal(content="reviewer feedback", confidence=0.7)
    out = b.step({"feedback": [fb]}, state)
    assert "reviewer feedback" in out.content
    assert "seed" in out.content


def test_battery_accumulate_ignores_zero_feedback():
    b = Battery({"content": "seed", "accumulate": True})
    state = {"user_prompt": "Q"}
    out = b.step({"feedback": [Signal.ZERO]}, state)
    assert out.content == "seed\nQ"


def test_battery_no_accumulate_ignores_feedback():
    b = Battery({"content": "seed", "accumulate": False})
    state = {"user_prompt": "Q"}
    fb = Signal(content="feedback content", confidence=0.9)
    out = b.step({"feedback": [fb]}, state)
    assert out.content == "seed\nQ"


# --- Resistor ---

def test_resistor_passes_above_threshold():
    r = Resistor({"threshold": 0.5})
    sig = Signal(content="pass", confidence=0.8)
    out = r.step({"context": [sig]}, {})
    assert out is sig


def test_resistor_passes_at_threshold():
    r = Resistor({"threshold": 0.5})
    sig = Signal(content="exact", confidence=0.5)
    out = r.step({"context": [sig]}, {})
    assert out is sig


def test_resistor_blocks_below_threshold():
    r = Resistor({"threshold": 0.5})
    sig = Signal(content="weak", confidence=0.3)
    out = r.step({"context": [sig]}, {})
    assert out is Signal.ZERO


def test_resistor_empty_inputs_returns_zero():
    r = Resistor({"threshold": 0.5})
    out = r.step({}, {})
    assert out is Signal.ZERO


def test_resistor_zero_input_returns_zero():
    r = Resistor({"threshold": 0.5})
    out = r.step({"context": [Signal.ZERO]}, {})
    assert out is Signal.ZERO


# --- AndGate ---

def test_and_gate_passes_all_above_threshold():
    g = AndGate({"threshold": 0.5})
    s1 = Signal(content="a", confidence=0.8)
    s2 = Signal(content="b", confidence=0.9)
    out = g.step({"context": [s1], "peer": [s2]}, {})
    assert out.confidence > 0
    assert "a" in out.content
    assert "b" in out.content


def test_and_gate_blocked_when_any_fails():
    g = AndGate({"threshold": 0.5})
    s1 = Signal(content="a", confidence=0.8)
    s2 = Signal(content="b", confidence=0.3)
    out = g.step({"context": [s1], "peer": [s2]}, {})
    assert out.confidence == 0.0
    assert out.contradiction == 1.0


def test_and_gate_blocked_has_contradiction_one():
    g = AndGate({"threshold": 0.6})
    weak = Signal(content="weak", confidence=0.4)
    out = g.step({"context": [weak]}, {})
    assert out.contradiction == 1.0


def test_and_gate_all_zero_inputs_blocked():
    g = AndGate({"threshold": 0.5})
    out = g.step({"context": [Signal.ZERO]}, {})
    assert out.contradiction == 1.0


def test_and_gate_empty_inputs_blocked():
    g = AndGate({"threshold": 0.5})
    out = g.step({}, {})
    assert out.contradiction == 1.0


# --- Sink ---

def test_sink_stores_highest_confidence():
    sink = Sink({})
    lo = Signal(content="low", confidence=0.3, relevance=0.5)
    hi = Signal(content="high", confidence=0.9, relevance=0.5)
    state = {}
    sink.step({"context": [lo, hi]}, state)
    assert state["last_input"] is hi


def test_sink_tiebreaks_by_relevance():
    sink = Sink({})
    a = Signal(content="a", confidence=0.8, relevance=0.3)
    b = Signal(content="b", confidence=0.8, relevance=0.9)
    state = {}
    sink.step({"context": [a, b]}, state)
    assert state["last_input"] is b


def test_sink_always_returns_zero():
    sink = Sink({})
    sig = Signal(content="anything", confidence=0.9)
    out = sink.step({"context": [sig]}, {})
    assert out is Signal.ZERO


def test_sink_does_not_overwrite_when_all_zero():
    sink = Sink({})
    prev = Signal(content="previous", confidence=0.7)
    state = {"last_input": prev}
    sink.step({"context": [Signal.ZERO]}, state)
    assert state["last_input"] is prev


def test_sink_does_not_set_last_input_on_empty():
    sink = Sink({})
    state = {}
    sink.step({}, state)
    assert "last_input" not in state
