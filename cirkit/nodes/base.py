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
        """Single-slot lazy cache for deterministic nodes (R12).

        Stores only the MOST RECENT (input-sig, output) pair — not a full history.
        Same inputs as last call -> return cached output; any change -> call step() again.
        Motor overrides this entirely (R2 bypass + multi-entry OrderedDict cache).
        """
        sig = tuple(
            s.content_hash()
            for role in sorted(inputs.keys())
            for s in inputs[role]
            if s is not Signal.ZERO  # C1: filter sentinels — consistent with Motor cache
        )
        if state.get("_last_sig") == sig and "_last_out" in state:
            return state["_last_out"]
        out = self.step(inputs, state)
        state["_last_sig"] = sig
        state["_last_out"] = out
        return out
