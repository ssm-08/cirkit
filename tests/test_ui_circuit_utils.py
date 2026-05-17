import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ui"))

from circuit_utils import validate_circuit  # noqa: E402


def base_circuit(**overrides):
    circuit = {
        "config": {"epsilon": 0.05, "max_iter": 4},
        "sink": "out",
        "nodes": [
            {"id": "src", "type": "battery", "config": {"content": "test"}},
            {"id": "out", "type": "sink", "config": {}},
        ],
        "wires": [{"from": "src", "to": "out", "role": "context"}],
    }
    circuit.update(overrides)
    return circuit


def test_validate_circuit_rejects_malformed_nodes_without_crashing():
    errors = validate_circuit(base_circuit(nodes=[{"type": "battery"}]))

    assert "node 0 missing id" in errors
    assert "sink 'out' not in nodes" in errors


def test_validate_circuit_accepts_router_branch_wires():
    circuit = base_circuit(
        nodes=[
            {"id": "src", "type": "battery", "config": {"content": "test"}},
            {
                "id": "route",
                "type": "router",
                "config": {
                    "rule": "by_confidence",
                    "branches": [
                        {"branch": "high", "min_confidence": 0.7},
                        {"branch": "default", "default": True},
                    ],
                },
            },
            {"id": "out", "type": "sink", "config": {}},
        ],
        wires=[
            {"from": "src", "to": "route", "role": "context"},
            {"from": "route", "to": "out", "branch": "high"},
        ],
    )

    assert validate_circuit(circuit) == []


def test_validate_circuit_rejects_router_role_wires():
    circuit = base_circuit(
        nodes=[
            {
                "id": "route",
                "type": "router",
                "config": {
                    "rule": "by_confidence",
                    "branches": [{"branch": "default", "default": True}],
                },
            },
            {"id": "out", "type": "sink", "config": {}},
        ],
        wires=[{"from": "route", "to": "out", "role": "context"}],
    )

    assert "wire from Router 'route' must have branch" in validate_circuit(circuit)
