from __future__ import annotations
from abc import ABC, abstractmethod
from cirkit.signal import Signal


class Node(ABC):
    """ABC for all circuit nodes.

    step() receives role-grouped inputs per R1:
      inputs keys: 'context', 'feedback', 'peer'
      values: list[Signal] (possibly empty, possibly containing Signal.ZERO)

    Always returns Signal, never None. Sink always returns Signal.ZERO.
    Private state dict persists across iterations — caller maintains it.
    """

    @abstractmethod
    def step(self, inputs: dict[str, list[Signal]], state: dict) -> Signal:
        raise NotImplementedError

    def _maybe_cached_step(self, inputs: dict[str, list[Signal]], state: dict) -> Signal:
        """Lazy step cache for deterministic nodes per R12.

        Cache key: tuple of content_hash() for all signals, sorted by role then order.
        Same inputs -> return cached output without calling step() again.
        Motor overrides this entirely (R2 contradiction bypass + its own cache logic).
        """
        sig = tuple(
            s.content_hash()
            for role in sorted(inputs.keys())
            for s in inputs[role]
        )
        if state.get("_last_sig") == sig and "_last_out" in state:
            return state["_last_out"]
        out = self.step(inputs, state)
        state["_last_sig"] = sig
        state["_last_out"] = out
        return out
