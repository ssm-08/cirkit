"""R11: Router branch routing."""
import pytest
from cirkit.signal import Signal
from cirkit.nodes.router import Router


def make_confidence_router():
    return Router({
        "rule": "by_confidence",
        "branches": [
            {"branch": "fast", "min_confidence": 0.85},
            {"branch": "slow", "default": True},
        ],
    })


def make_length_router():
    return Router({
        "rule": "by_content_length",
        "branches": [
            {"branch": "short", "max_length": 20},
            {"branch": "long", "default": True},
        ],
    })


def make_flag_router():
    return Router({
        "rule": "by_flag",
        "branches": [
            {"branch": "fast", "flag_name": "fast"},
            {"branch": "default", "default": True},
        ],
    })


# --- by_confidence ---

def test_by_confidence_high_routes_to_fast():
    r = make_confidence_router()
    sig = Signal(content="query", confidence=0.9)
    state = {}
    r.step({"context": [sig]}, state)
    assert state["routed_branch"] == "fast"


def test_by_confidence_low_routes_to_default():
    r = make_confidence_router()
    sig = Signal(content="query", confidence=0.5)
    state = {}
    r.step({"context": [sig]}, state)
    assert state["routed_branch"] == "slow"


def test_by_confidence_at_threshold_routes_to_fast():
    r = make_confidence_router()
    sig = Signal(content="query", confidence=0.85)
    state = {}
    r.step({"context": [sig]}, state)
    assert state["routed_branch"] == "fast"


# --- by_content_length ---

def test_by_content_length_short_routes_to_short():
    r = make_length_router()
    sig = Signal(content="short text", confidence=0.8)
    state = {}
    r.step({"context": [sig]}, state)
    assert state["routed_branch"] == "short"


def test_by_content_length_long_routes_to_default():
    r = make_length_router()
    sig = Signal(content="this is a much longer content string exceeding limit", confidence=0.8)
    state = {}
    r.step({"context": [sig]}, state)
    assert state["routed_branch"] == "long"


# --- by_flag ---

def test_by_flag_match():
    r = make_flag_router()
    sig = Signal(content="q", confidence=0.8, flags={"fast": True})
    state = {}
    r.step({"context": [sig]}, state)
    assert state["routed_branch"] == "fast"


def test_by_flag_no_match_uses_default():
    r = make_flag_router()
    sig = Signal(content="q", confidence=0.8, flags={})
    state = {}
    r.step({"context": [sig]}, state)
    assert state["routed_branch"] == "default"


# --- branch_outputs contract ---

def test_matched_branch_gets_signal():
    r = make_confidence_router()
    sig = Signal(content="query", confidence=0.9)
    state = {}
    r.step({"context": [sig]}, state)
    assert r.get_branch_output("fast", state) is sig


def test_unmatched_branch_gets_zero():
    r = make_confidence_router()
    sig = Signal(content="query", confidence=0.9)
    state = {}
    r.step({"context": [sig]}, state)
    assert r.get_branch_output("slow", state) is Signal.ZERO


def test_exactly_one_branch_gets_real_signal():
    r = make_confidence_router()
    sig = Signal(content="query", confidence=0.9)
    state = {}
    r.step({"context": [sig]}, state)
    branch_outputs = state["branch_outputs"]
    real_signals = [v for v in branch_outputs.values() if v is not Signal.ZERO]
    assert len(real_signals) == 1


def test_step_returns_zero():
    r = make_confidence_router()
    sig = Signal(content="query", confidence=0.9)
    state = {}
    out = r.step({"context": [sig]}, state)
    assert out is Signal.ZERO


def test_unknown_rule_raises():
    r = Router({"rule": "by_magic", "branches": [{"branch": "x", "default": True}]})
    sig = Signal(content="q", confidence=0.5)
    with pytest.raises(ValueError, match="Unknown Router rule"):
        r.step({"context": [sig]}, {})
