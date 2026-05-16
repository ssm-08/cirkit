from cirkit.nodes.base import Node
from cirkit.signal import Signal


class Sink(Node):
    """Terminal node. Records highest-confidence incoming signal; always returns Signal.ZERO.

    Stores selected signal in state['last_input']. Tie-break by relevance (higher wins).
    Engine reads state['last_input'] after loop for final output.
    Sink contributes 0 to aggregate delta (constant ZERO output) — correct per plan G16.
    No out-edges allowed (validated at load time in graph.py).
    """

    def __init__(self, config: dict):
        self.config = config

    def step(self, inputs: dict, state: dict) -> Signal:
        all_sigs = [
            s for signals in inputs.values()
            for s in signals
            if s is not Signal.ZERO and s.content
        ]
        if all_sigs:
            best = max(all_sigs, key=lambda s: (s.confidence, s.relevance))
            state["last_input"] = best
        return Signal.ZERO
