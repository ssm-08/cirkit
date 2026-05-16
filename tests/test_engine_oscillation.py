"""max_iter safety net: oscillating node prevents convergence."""
import json
import os
import tempfile

import pytest

from cirkit.graph import load_circuit
from cirkit.engine import run
from cirkit.signal import Signal
from cirkit.nodes.base import Node
from cirkit.nodes import NODE_REGISTRY


class Oscillator(Node):
    """Alternates output content A/B every iteration regardless of input.
    Overrides _maybe_cached_step to bypass caching — each call increments state counter.
    """

    def __init__(self, config: dict):
        self.config = config

    def step(self, inputs: dict, state: dict) -> Signal:
        count = state.get("count", 0)
        state["count"] = count + 1
        content = "A" if count % 2 == 0 else "B"
        return Signal(content=content, confidence=0.5)

    def _maybe_cached_step(self, inputs: dict, state: dict) -> Signal:
        # Bypass caching so oscillation persists despite stable inputs
        return self.step(inputs, state)


def _write_tmp(data):
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(data, f)
    f.close()
    return f.name


def test_oscillation_runs_to_max_iter():
    NODE_REGISTRY["oscillator"] = Oscillator
    data = {
        "config": {"epsilon": 0.01, "max_iter": 5},
        "sink": "out",
        "nodes": [
            {"id": "ctx",  "type": "battery",    "config": {"content": "seed", "accumulate": False}},
            {"id": "osc",  "type": "oscillator",  "config": {}},
            {"id": "out",  "type": "sink",        "config": {}}
        ],
        "wires": [
            {"from": "ctx", "to": "osc", "role": "context"},
            {"from": "osc", "to": "out", "role": "context"}
        ]
    }
    path = _write_tmp(data)
    try:
        circuit = load_circuit(path)
        result = run(circuit, "test oscillation")
        assert result.converged is False
        assert result.iterations == 5
    finally:
        os.unlink(path)
        del NODE_REGISTRY["oscillator"]


def test_oscillation_no_exception():
    NODE_REGISTRY["oscillator"] = Oscillator
    data = {
        "config": {"epsilon": 0.01, "max_iter": 5},
        "sink": "out",
        "nodes": [
            {"id": "ctx", "type": "battery",   "config": {"content": "seed", "accumulate": False}},
            {"id": "osc", "type": "oscillator", "config": {}},
            {"id": "out", "type": "sink",       "config": {}}
        ],
        "wires": [
            {"from": "ctx", "to": "osc", "role": "context"},
            {"from": "osc", "to": "out", "role": "context"}
        ]
    }
    path = _write_tmp(data)
    try:
        circuit = load_circuit(path)
        result = run(circuit, "no error expected")
        # Must not raise; delta_history should have entries
        assert len(result.delta_history) == 5
    finally:
        os.unlink(path)
        del NODE_REGISTRY["oscillator"]


def test_oscillation_final_delta_above_epsilon():
    NODE_REGISTRY["oscillator"] = Oscillator
    data = {
        "config": {"epsilon": 0.01, "max_iter": 5},
        "sink": "out",
        "nodes": [
            {"id": "ctx", "type": "battery",   "config": {"content": "seed", "accumulate": False}},
            {"id": "osc", "type": "oscillator", "config": {}},
            {"id": "out", "type": "sink",       "config": {}}
        ],
        "wires": [
            {"from": "ctx", "to": "osc", "role": "context"},
            {"from": "osc", "to": "out", "role": "context"}
        ]
    }
    path = _write_tmp(data)
    try:
        circuit = load_circuit(path)
        result = run(circuit, "delta test")
        epsilon = circuit.config.get("epsilon", 0.01)
        # At least one delta must be above epsilon for non-convergence
        assert any(d >= epsilon for d in result.delta_history)
    finally:
        os.unlink(path)
        del NODE_REGISTRY["oscillator"]
