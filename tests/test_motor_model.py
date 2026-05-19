"""Tests for per-Motor --model flag pass-through."""
import pytest
from unittest.mock import patch
from cirkit.nodes.motor import Motor
from cirkit.signal import Signal
from cirkit import llm


def _llm_result():
    return llm.LLMResult(content='ok. {"confidence": 0.8}', tokens_in=10, tokens_out=5, cost_usd=0.001)


def _make_signal(content):
    return Signal(content=content, confidence=0.8)


def test_model_flag_passed_when_configured():
    motor = Motor({"system": "test", "model": "haiku"})
    state = {}
    inputs = {"context": [_make_signal("ctx")]}
    with patch("cirkit.llm.call_claude", return_value=_llm_result()) as mock:
        motor._call_llm(inputs, state)
    assert mock.call_args[1]["model"] == "haiku"


def test_model_flag_omitted_when_not_configured():
    motor = Motor({"system": "test"})
    state = {}
    inputs = {"context": [_make_signal("ctx")]}
    with patch("cirkit.llm.call_claude", return_value=_llm_result()) as mock:
        motor._call_llm(inputs, state)
    assert mock.call_args[1]["model"] is None


def test_model_stored_on_motor():
    motor = Motor({"system": "test", "model": "claude-haiku-4-5-20251001"})
    assert motor.model == "claude-haiku-4-5-20251001"


def test_no_model_field_gives_none():
    motor = Motor({"system": "test"})
    assert motor.model is None
