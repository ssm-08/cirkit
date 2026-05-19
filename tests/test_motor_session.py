"""Tests for per-Motor session_id uniqueness and token_usage aggregation."""
import json
import pytest
from unittest.mock import patch
from cirkit.nodes.motor import Motor
from cirkit.signal import Signal
from cirkit import llm
from cirkit.graph import load_circuit
from cirkit.engine import run


def _llm_result(tokens_in=100, tokens_out=50, cost=0.002):
    return llm.LLMResult(
        content='answer. {"confidence": 0.8}',
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=cost,
    )


def _make_signal(content):
    return Signal(content=content, confidence=0.8)


def test_session_id_passed_to_llm():
    motor = Motor({"system": "test"})
    state = {"session_id": "aabbccdd-1234-5678-abcd-000000000000"}
    inputs = {"context": [_make_signal("ctx")]}
    with patch("cirkit.llm.call_claude", return_value=_llm_result()) as mock:
        motor._call_llm(inputs, state)
    assert mock.call_args[1]["session_id"] == "aabbccdd-1234-5678-abcd-000000000000"


def test_no_session_id_still_works():
    motor = Motor({"system": "test"})
    state = {}
    inputs = {"context": [_make_signal("ctx")]}
    with patch("cirkit.llm.call_claude", return_value=_llm_result()) as mock:
        sig = motor._call_llm(inputs, state)
    assert mock.call_args[1]["session_id"] is None
    assert sig is not Signal.ZERO


def test_token_usage_and_delta_flag_across_two_calls():
    """Combines: token accumulation per call + delta flag on second call."""
    motor = Motor({"system": "test"})
    state = {"session_id": "test-uuid", "token_usage": []}
    inputs_1 = {"context": [_make_signal("first")]}
    inputs_2 = {"context": [_make_signal("first")], "feedback": [_make_signal("refine")]}
    with patch("cirkit.llm.call_claude", return_value=_llm_result(100, 50, 0.002)):
        motor._call_llm(inputs_1, state)
    with patch("cirkit.llm.call_claude", return_value=_llm_result(20, 30, 0.001)):
        motor._call_llm(inputs_2, state)
    assert len(state["token_usage"]) == 2
    assert state["token_usage"][0]["tokens_in"] == 100
    assert state["token_usage"][1]["tokens_in"] == 20
    assert abs(sum(e["cost_usd"] for e in state["token_usage"]) - 0.003) < 1e-9
    assert state["token_usage"][0]["delta"] is False
    assert state["token_usage"][1]["delta"] is True


def test_engine_assigns_unique_session_ids_per_motor(tmp_path):
    """Each Motor in a circuit gets a distinct UUID per run."""
    circuit_data = {
        "config": {"epsilon": 0.05, "max_iter": 1},
        "sink": "out",
        "nodes": [
            {"id": "src", "type": "battery", "config": {"content": "test"}},
            {"id": "m1",  "type": "motor",   "config": {"system": "motor 1"}},
            {"id": "m2",  "type": "motor",   "config": {"system": "motor 2"}},
            {"id": "out", "type": "sink",    "config": {}},
        ],
        "wires": [
            {"from": "src", "to": "m1",  "role": "context"},
            {"from": "src", "to": "m2",  "role": "context"},
            {"from": "m1",  "to": "out", "role": "context"},
            {"from": "m2",  "to": "out", "role": "context"},
        ],
    }
    circuit_file = tmp_path / "two_motor.json"
    circuit_file.write_text(json.dumps(circuit_data))
    circuit = load_circuit(str(circuit_file))

    seen_sessions = []

    def capture_llm(prompt, *, session_id=None, model=None, timeout=60):
        if session_id:
            seen_sessions.append(session_id)
        return llm.LLMResult(content='ok. {"confidence": 0.9}')

    with patch("cirkit.llm.call_claude", capture_llm):
        run(circuit, "test")

    assert len(seen_sessions) == 2
    assert len(set(seen_sessions)) == 2, "Motor session IDs must be unique per run"
