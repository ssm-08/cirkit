"""Tests for Motor empty-input short-circuit (no LLM call when all inputs are ZERO)."""
import pytest
from unittest.mock import patch
from cirkit.nodes.motor import Motor
from cirkit.signal import Signal
from cirkit import llm


def _llm_result():
    return llm.LLMResult(content='ok. {"confidence": 0.8}')


@pytest.mark.parametrize("inputs", [
    {"context": [Signal.ZERO], "peer": [Signal.ZERO]},
    {},
])
def test_no_llm_call_when_no_content(inputs):
    motor = Motor({"system": "test"})
    state = {}
    with patch("cirkit.llm.call_claude", return_value=_llm_result()) as mock:
        result = motor._call_llm(inputs, state)
    mock.assert_not_called()
    assert result is Signal.ZERO


@pytest.mark.parametrize("inputs", [
    {"context": [Signal(content="real content", confidence=0.9)]},
    {"context": [Signal.ZERO], "feedback": [Signal(content="refine this", confidence=0.5)]},
])
def test_llm_called_when_any_role_has_content(inputs):
    motor = Motor({"system": "test"})
    state = {}
    with patch("cirkit.llm.call_claude", return_value=_llm_result()) as mock:
        motor._call_llm(inputs, state)
    mock.assert_called_once()


def test_signal_zero_not_recorded_in_token_usage():
    motor = Motor({"system": "test"})
    state = {}
    inputs = {"context": [Signal.ZERO]}
    with patch("cirkit.llm.call_claude", return_value=_llm_result()):
        motor._call_llm(inputs, state)
    assert state.get("token_usage", []) == []
