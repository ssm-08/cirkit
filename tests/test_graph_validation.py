"""Tests for graph.py validation: cycles, accumulate, reachability, isinstance."""
import json
import os
import tempfile
import warnings

import pytest

from cirkit.graph import load_circuit


def _write_tmp(data):
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(data, f)
    f.close()
    return f.name


def test_i1_motor_registered_via_nodes_package():
    """I1: 'motor' must be in NODE_REGISTRY after importing cirkit.nodes alone."""
    from cirkit.nodes import NODE_REGISTRY
    assert "motor" in NODE_REGISTRY, (
        "Motor not in NODE_REGISTRY — registration must happen in nodes/__init__.py"
    )


def test_i4_self_loop_context_raises():
    """I4: Self-loop on context role must be rejected."""
    data = {
        "config": {"epsilon": 0.05, "max_iter": 5},
        "sink": "out",
        "nodes": [
            {"id": "a", "type": "battery", "config": {"content": "x", "accumulate": False}},
            {"id": "b", "type": "resistor", "config": {"threshold": 0.5}},
            {"id": "out", "type": "sink", "config": {}},
        ],
        "wires": [
            {"from": "a", "to": "b", "role": "context"},
            {"from": "b", "to": "out", "role": "context"},
            {"from": "b", "to": "b", "role": "context"},   # self-loop
        ],
    }
    path = _write_tmp(data)
    try:
        with pytest.raises(ValueError, match="structural cycle"):
            load_circuit(path)
    finally:
        os.unlink(path)


def test_i4_context_cycle_between_two_nodes_raises():
    """I4: A → B → A via context wires must be rejected."""
    data = {
        "config": {"epsilon": 0.05, "max_iter": 5},
        "sink": "out",
        "nodes": [
            {"id": "a", "type": "resistor", "config": {"threshold": 0.5}},
            {"id": "b", "type": "resistor", "config": {"threshold": 0.5}},
            {"id": "out", "type": "sink", "config": {}},
        ],
        "wires": [
            {"from": "a", "to": "b", "role": "context"},
            {"from": "b", "to": "a", "role": "context"},   # cycle
            {"from": "b", "to": "out", "role": "context"},
        ],
    }
    path = _write_tmp(data)
    try:
        with pytest.raises(ValueError, match="structural cycle"):
            load_circuit(path)
    finally:
        os.unlink(path)


def test_i4_feedback_cycle_allowed():
    """I4: Feedback back-edges must NOT trigger cycle detection."""
    data = {
        "config": {"epsilon": 0.05, "max_iter": 5},
        "sink": "out",
        "nodes": [
            {"id": "ctx", "type": "battery", "config": {"content": "x", "accumulate": True}},
            {"id": "gate", "type": "and_gate", "config": {"threshold": 0.5, "early_exit_threshold": 0.99}},
            {"id": "out", "type": "sink", "config": {}},
        ],
        "wires": [
            {"from": "ctx", "to": "gate", "role": "context"},
            {"from": "gate", "to": "out", "role": "context"},
            {"from": "gate", "to": "ctx", "role": "feedback"},   # valid back-edge
        ],
    }
    path = _write_tmp(data)
    try:
        circuit = load_circuit(path)   # must not raise
        assert circuit is not None
    finally:
        os.unlink(path)
