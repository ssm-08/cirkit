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
        return self.step(inputs, state)


@pytest.fixture(autouse=True)
def register_oscillator():
    NODE_REGISTRY["oscillator"] = Oscillator
    yield
    NODE_REGISTRY.pop("oscillator", None)


@pytest.fixture
def oscillator_circuit(tmp_path):
    data = {
        "config": {"epsilon": 0.01, "max_iter": 5},
        "sink": "out",
        "nodes": [
            {"id": "ctx", "type": "battery",    "config": {"content": "seed", "accumulate": False}},
            {"id": "osc", "type": "oscillator",  "config": {}},
            {"id": "out", "type": "sink",        "config": {}}
        ],
        "wires": [
            {"from": "ctx", "to": "osc", "role": "context"},
            {"from": "osc", "to": "out", "role": "context"}
        ]
    }
    path = tmp_path / "osc.json"
    path.write_text(json.dumps(data))
    return load_circuit(str(path))


def test_oscillation_does_not_converge(oscillator_circuit):
    result = run(oscillator_circuit, "test")
    assert result.converged is False
    assert result.iterations == 5
    assert len(result.delta_history) == 5
    epsilon = oscillator_circuit.config.get("epsilon", 0.01)
    assert any(d >= epsilon for d in result.delta_history)
