import json
import os
import tempfile
from unittest import mock

import pytest

import cirkit.nodes.base
from cirkit.graph import load_circuit
from cirkit.engine import run
from cirkit.signal import Signal
from cirkit.state import RunResult
from cirkit.convergence import aggregate_delta as _real_agg


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


def test_all_cached_after_stable_converges():
    """Battery stable after iter 1, downstream after iter 2 → all cached → agg=0.0 → converged."""
    circuit_def = {
        "config": {"epsilon": 0.05, "max_iter": 10},
        "sink": "out",
        "nodes": SIMPLE_CIRCUIT["nodes"],
        "wires": SIMPLE_CIRCUIT["wires"],
    }
    path = _write_tmp(circuit_def)
    try:
        circuit = load_circuit(path)
        result = run(circuit, "test")
        assert result.converged is True
        assert result.iterations <= 3
    finally:
        os.unlink(path)


def test_battery_excluded_from_delta_after_iter1():
    """Battery (ctx) must not appear in aggregate_delta calls after iteration 1."""
    path = _write_tmp(SIMPLE_CIRCUIT)
    try:
        circuit = load_circuit(path)
        calls = []

        def _recording(prev, curr):
            calls.append(set(prev.keys()))
            return _real_agg(prev, curr)

        with mock.patch("cirkit.engine.aggregate_delta", side_effect=_recording):
            result = run(circuit, "test")

        # calls[0] = iter 1. After iter 1, battery is cached → excluded from miss set.
        assert len(calls) >= 1, "aggregate_delta never called — circuit may have trivially converged"
        for node_ids in calls[1:]:
            assert "ctx" not in node_ids, f"battery 'ctx' found in delta call after iter 1: {node_ids}"
    finally:
        os.unlink(path)


def test_sink_never_in_delta():
    """Sink (out) always returns Signal.ZERO → always a cache hit → never in aggregate_delta."""
    path = _write_tmp(SIMPLE_CIRCUIT)
    try:
        circuit = load_circuit(path)
        calls = []

        def _recording(prev, curr):
            calls.append(set(prev.keys()))
            return _real_agg(prev, curr)

        with mock.patch("cirkit.engine.aggregate_delta", side_effect=_recording):
            result = run(circuit, "test")

        for node_ids in calls:
            assert "out" not in node_ids, f"sink 'out' found in delta call: {node_ids}"
    finally:
        os.unlink(path)


def test_empty_miss_returns_zero_agg_converges():
    """All nodes return same Signal object → miss set empty → agg=0.0 → converged in iter 1."""
    path = _write_tmp(SIMPLE_CIRCUIT)
    try:
        circuit = load_circuit(path)
        fixed = Signal(content="fixed", confidence=0.8)

        with mock.patch.object(
            cirkit.nodes.base.Node, "_maybe_cached_step", return_value=fixed
        ):
            result = run(circuit, "test")

        assert result.converged is True
        assert result.iterations <= 2  # bootstrap seeds battery; res/gate/out start ZERO → 1 miss iter
    finally:
        os.unlink(path)


def test_active_node_included_in_delta_on_first_miss():
    """On iter 1, and_gate (gate) has a cache miss — must appear in aggregate_delta."""
    path = _write_tmp(SIMPLE_CIRCUIT)
    try:
        circuit = load_circuit(path)
        calls = []

        def _recording(prev, curr):
            calls.append(set(prev.keys()))
            return _real_agg(prev, curr)

        with mock.patch("cirkit.engine.aggregate_delta", side_effect=_recording):
            result = run(circuit, "test")

        assert len(calls) >= 1, "aggregate_delta never called"
        assert "gate" in calls[0], f"gate not in iter 1 delta call: {calls[0]}"
    finally:
        os.unlink(path)


def test_existing_convergence_behavior_preserved():
    """Regression: cache-miss scoping must not break existing circuit behavior."""
    path = _write_tmp(SIMPLE_CIRCUIT)
    try:
        circuit = load_circuit(path)
        result = run(circuit, "test")
        assert result.converged is True
        assert result.iterations <= 3
        assert "Hello world." in result.output.content
    finally:
        os.unlink(path)
