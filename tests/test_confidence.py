"""Tests for confidence.parse_confidence: hedge detection and JSON parsing."""
import pytest
from cirkit.confidence import parse_confidence


# --- M8: fullmatch prevents mid-line confidence extraction ---

def test_m8_confidence_json_entire_last_line():
    """M8: {"confidence": X} as the full last line is extracted."""
    raw = 'The answer is 42.\n{"confidence": 0.9}'
    content, conf = parse_confidence(raw)
    assert conf == pytest.approx(0.9)
    assert "The answer is 42." in content


def test_m8_confidence_json_mid_line_not_extracted():
    """M8: {"confidence": X} embedded mid-line must NOT be parsed as explicit confidence."""
    # Last line has extra text after the JSON blob -> fullmatch fails -> fallback used
    raw = 'The answer is 42.\n{"confidence": 0.9} and more text'
    content, conf = parse_confidence(raw)
    # conf must be the fallback (length-based), not 0.9
    assert conf != pytest.approx(0.9)
    assert content.strip() != ""   # content is the full raw (not truncated)


# --- I5: word-boundary hedge matching ---

def test_i5_await_does_not_trigger_hedge():
    """I5: 'await' must not match hedge phrase 'wait'."""
    # Long content so fallback conf is above 0.5 without hedge
    raw = "await the result from the server, it will respond shortly. " * 10
    _, conf = parse_confidence(raw)
    assert conf > 0.5


def test_i5_factually_does_not_trigger_hedge():
    """I5: 'factually' must not match hedge phrase 'actually'."""
    raw = "This is factually correct and provably true. " * 10
    _, conf = parse_confidence(raw)
    assert conf > 0.5


def test_i5_actually_alone_does_trigger_hedge():
    """I5: bare 'actually' IS a hedge phrase and MUST cap confidence when no explicit JSON."""
    raw = "actually I need to reconsider this. " * 5
    _, conf = parse_confidence(raw)
    assert conf <= 0.5


def test_i5_wait_alone_does_trigger_hedge():
    """I5: bare 'wait' IS a hedge phrase and MUST cap confidence when no explicit JSON."""
    raw = "wait, that's not right. Let me think again. " * 5
    _, conf = parse_confidence(raw)
    assert conf <= 0.5


def test_i5_hedge_does_not_override_explicit_confidence():
    """I5: When explicit {"confidence": X} is present, hedge phrases must NOT cap it."""
    raw = 'actually this is correct and well-reasoned.\n{"confidence": 0.9}'
    _, conf = parse_confidence(raw)
    assert conf == pytest.approx(0.9), (
        "Hedge phrase should not cap confidence when an explicit JSON token was found"
    )


# --- Existing edge cases (regression) ---

def test_empty_input_returns_low_confidence():
    assert parse_confidence("") == ("", 0.1)
    assert parse_confidence("   ") == ("", 0.1)


def test_explicit_confidence_clamped_to_1():
    raw = 'ok\n{"confidence": 1.5}'
    _, conf = parse_confidence(raw)
    assert conf == pytest.approx(1.0)


def test_explicit_confidence_clamped_to_0():
    raw = 'ok\n{"confidence": -0.5}'
    _, conf = parse_confidence(raw)
    assert conf == pytest.approx(0.0)
