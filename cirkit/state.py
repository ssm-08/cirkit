from __future__ import annotations
from dataclasses import dataclass, field
from cirkit.signal import Signal


@dataclass
class RunState:
    outputs: dict = field(default_factory=dict)       # node_id -> Signal
    node_state: dict = field(default_factory=dict)    # node_id -> dict (persists across iters)
    delta_history: list = field(default_factory=list) # float per iteration
    iteration: int = 0


@dataclass
class RunResult:
    output: Signal
    iterations: int
    converged: bool
    delta_history: list
    all_outputs: dict  # node_id -> Signal (final iteration snapshot)
