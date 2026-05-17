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
