import math
from cirkit.signal import Signal


def delta(prev: Signal, curr: Signal) -> float:
    """0.6*metric_dist + 0.4*content_change. See plan convergence math section.

    metric_dist   = euclidean(prev_metrics, curr_metrics) / 2.0  (normalized to [0,1])
    content_change = 0.0 if hash(prev) == hash(curr) else 1.0   (binary)
    """
    v1 = prev.metrics_vector()
    v2 = curr.metrics_vector()
    metric_dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(v1, v2))) / 2.0
    content_change = 0.0 if prev.content_hash() == curr.content_hash() else 1.0
    return 0.6 * metric_dist + 0.4 * content_change


def aggregate_delta(prev_outputs: dict, curr_outputs: dict) -> float:
    """Mean delta across all nodes. Empty dict returns 0.0."""
    if not prev_outputs:
        return 0.0
    assert prev_outputs.keys() == curr_outputs.keys(), (
        f"aggregate_delta: key mismatch — "
        f"prev={set(prev_outputs)} curr={set(curr_outputs)}"
    )
    return sum(delta(prev_outputs[n], curr_outputs[n]) for n in prev_outputs) / len(prev_outputs)
