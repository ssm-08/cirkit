from cirkit.nodes.base import Node
from cirkit.signal import Signal


class Resistor(Node):
    """Single-input threshold gate.

    confidence >= cfg['threshold'] -> pass through input unchanged.
    confidence < cfg['threshold']  -> return Signal.ZERO.

    Not attenuation. Not None. Signal.ZERO is unambiguous downstream.
    If no input present: return Signal.ZERO.
    """

    def __init__(self, config: dict):
        self.threshold = config["threshold"]

    def step(self, inputs: dict, state: dict) -> Signal:
        signal = inputs.get("context", [Signal.ZERO])[0] if inputs.get("context") else Signal.ZERO
        if signal is Signal.ZERO or signal.confidence < self.threshold:
            return Signal.ZERO
        return signal
