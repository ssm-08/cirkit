import json
import os
import tempfile

import pytest

from cirkit.graph import load_circuit
from cirkit.engine import run
from cirkit.signal import Signal
from cirkit.state import RunResult


SIMPLE_CIRCUIT = {
    "config": {"epsilon": 0.05, "max_iter": 5},
    "sink": "out",
    "nodes": [
        {"id": "ctx",  "type": "battery",  "config": {"content": "Hello world.", "accumulate": False}},
        {"id": "res",  "type": "resistor", "config": {"threshold": 0.5}},
        {"id": "gate", "type": "and_gate", "config": {"threshold": 0.5, "early_exit_threshold": 0.99}},
        {"id": "out",  "type": "sink",     "config": {}}
    ],
    "wires": [
        {"from": "ctx",  "to": "res",  "role": "context"},
        {"from": "res",  "to": "gate", "role": "peer"},
        {"from": "gate", "to": "out",  "role": "context"}
    ]
}


def _write_tmp(data):
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(data, f)
    f.close()
    return f.name


def test_engine_runs_without_motor():
    path = _write_tmp(SIMPLE_CIRCUIT)
    try:
        circuit = load_circuit(path)
        result = run(circuit, "test prompt")
        assert result.converged is True
        assert result.iterations <= 3
        assert result.output.content != ""
        assert "Hello world." in result.output.content
    finally:
        os.unlink(path)


def test_engine_injects_user_prompt():
    path = _write_tmp(SIMPLE_CIRCUIT)
    try:
        circuit = load_circuit(path)
        result = run(circuit, "my test prompt")
        assert "my test prompt" in result.output.content
    finally:
        os.unlink(path)


def test_engine_result_type():
    path = _write_tmp(SIMPLE_CIRCUIT)
    try:
        circuit = load_circuit(path)
        result = run(circuit, "test")
        assert isinstance(result, RunResult)
        assert isinstance(result.converged, bool)
        assert isinstance(result.delta_history, list)
        assert all(isinstance(d, float) for d in result.delta_history)
    finally:
        os.unlink(path)


def test_delta_history_nonempty():
    path = _write_tmp(SIMPLE_CIRCUIT)
    try:
        circuit = load_circuit(path)
        result = run(circuit, "test")
        assert len(result.delta_history) >= 1
    finally:
        os.unlink(path)


def test_no_motor_import_needed():
    """Engine must work on circuits that contain no Motor nodes whatsoever."""
    from cirkit.nodes import NODE_REGISTRY
    # SIMPLE_CIRCUIT uses only battery/resistor/and_gate/sink — no motor
    assert not any(
        type(n).__name__ == "Motor"
        for n in load_circuit(_write_tmp(SIMPLE_CIRCUIT)).nodes.values()
        # verify at the circuit level, not registry level
    )
    path = _write_tmp(SIMPLE_CIRCUIT)
    try:
        circuit = load_circuit(path)
        result = run(circuit, "no motor needed")
        assert result.converged is True
    finally:
        os.unlink(path)


def test_nonconvergent_circuit_returns_false_not_raises():
    """max_iter=1 with a circuit that won't converge in one iteration."""
    data = {
        "config": {"epsilon": 0.0001, "max_iter": 1},
        "sink": "out",
        "nodes": [
            {"id": "ctx",  "type": "battery",  "config": {"content": "hi", "accumulate": False}},
            {"id": "gate", "type": "and_gate", "config": {"threshold": 0.5, "early_exit_threshold": 0.99}},
            {"id": "out",  "type": "sink",     "config": {}}
        ],
        "wires": [
            {"from": "ctx",  "to": "gate", "role": "context"},
            {"from": "gate", "to": "out",  "role": "context"}
        ]
    }
    path = _write_tmp(data)
    try:
        circuit = load_circuit(path)
        result = run(circuit, "prompt")
        assert isinstance(result, RunResult)
        assert result.converged is False
    finally:
        os.unlink(path)
