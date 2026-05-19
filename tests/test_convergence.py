import math
import pytest
from cirkit.signal import Signal
from cirkit.convergence import delta, aggregate_delta


SATURATED = Signal(content="x", confidence=1.0, contradiction=1.0, urgency=1.0, relevance=1.0)


@pytest.mark.parametrize("s", [
    Signal.ZERO,
    Signal(content="hello", confidence=0.7, contradiction=0.1, urgency=0.3, relevance=0.5),
])
def test_delta_same_signal_is_zero(s):
    assert delta(s, s) == 0.0


def test_delta_zero_to_saturated_equals_one():
    # content changed (0.1) + metrics from all-0 to all-1 (euclidean=2.0, /2.0=1.0, *0.9=0.9) = 1.0
    result = delta(Signal.ZERO, SATURATED)
    assert math.isclose(result, 1.0, rel_tol=1e-9)


def test_delta_content_only_change():
    # same metrics (all zero), different content -> 0.0*0.9 + 1.0*0.1 = 0.1
    s1 = Signal(content="aaa")
    s2 = Signal(content="bbb")
    result = delta(s1, s2)
    assert math.isclose(result, 0.1, rel_tol=1e-9)


def test_delta_metrics_only_saturated_change():
    # same content hash, metrics 0->1 on all channels
    # euclidean([0,0,0,0], [1,1,1,1]) = sqrt(4) = 2.0, /2.0 = 1.0, *0.9 = 0.9
    s1 = Signal(content="same")
    s2 = Signal(content="same", confidence=1.0, contradiction=1.0, urgency=1.0, relevance=1.0)
    result = delta(s1, s2)
    assert math.isclose(result, 0.9, rel_tol=1e-9)


def test_aggregate_delta_empty_returns_zero():
    assert aggregate_delta({}, {}) == 0.0


def test_aggregate_delta_single_node_same_as_delta():
    s1 = Signal(content="a", confidence=0.3)
    s2 = Signal(content="b", confidence=0.8)
    expected = delta(s1, s2)
    result = aggregate_delta({"n": s1}, {"n": s2})
    assert math.isclose(result, expected, rel_tol=1e-9)


def test_aggregate_delta_same_signals_zero():
    s = Signal(content="x", confidence=0.5)
    assert aggregate_delta({"a": s}, {"a": s}) == 0.0


def test_m1_aggregate_delta_key_mismatch_raises():
    """M1: aggregate_delta with mismatched dicts must raise RuntimeError."""
    from cirkit.convergence import aggregate_delta
    from cirkit.signal import Signal
    s = Signal(content="x", confidence=0.5)
    prev = {"a": s, "b": s}
    curr = {"a": s}          # missing "b"
    with pytest.raises(RuntimeError):
        aggregate_delta(prev, curr)


def test_aggregate_delta_mean_of_multiple():
    s1 = Signal(content="a")
    s2 = Signal(content="b")
    # delta(s1, s2) = 0.1 (content only)
    # delta(Signal.ZERO, Signal.ZERO) = 0.0
    expected = (0.1 + 0.0) / 2
    result = aggregate_delta({"x": s1, "y": Signal.ZERO}, {"x": s2, "y": Signal.ZERO})
    assert math.isclose(result, expected, rel_tol=1e-9)
