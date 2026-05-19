# Python API

## load_circuit

```python
from cirkit import load_circuit

circuit = load_circuit("examples/pr_review.json")
```

Loads and validates a circuit JSON file. Returns a `Circuit` object.

Raises `ValueError` with a descriptive message on:

- Invalid JSON or missing top-level fields
- Unknown node types
- Circuit topology errors (cycles, invalid sink, etc.)
- Missing required node config fields

## run

```python
from cirkit import run

result = run(
    circuit,
    user_prompt="Review this PR: adds retry logic to payment service",
    epsilon=None,       # uses circuit's config.epsilon if None
    max_iter=None,      # uses circuit's config.max_iter if None
    on_iter=None,       # optional callback
)
```

Runs the circuit and returns a `RunResult`.

**Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `circuit` | `Circuit` | Loaded circuit object from `load_circuit()` |
| `user_prompt` | `str` | The user's input; injected into all Battery nodes |
| `epsilon` | `float \| None` | Override circuit epsilon; `None` uses circuit default |
| `max_iter` | `int \| None` | Override max iterations; `None` uses circuit default |
| `on_iter` | `callable \| None` | Called after each iteration with `(iteration, outputs, delta)` |

## RunResult

```python
@dataclass
class RunResult:
    output: Signal          # Final output from the Sink node
    iterations: int         # Number of iterations that ran
    converged: bool         # True if delta < epsilon before max_iter
    delta_history: list     # [float] per-iteration aggregate delta values
    all_outputs: dict       # {node_id: Signal} final outputs for all nodes
```

## Signal

```python
from cirkit import Signal

sig = Signal(
    content="The PR looks correct.",
    confidence=0.85,
    contradiction=0.0,
    urgency=0.5,
    relevance=0.5,
    flags={"consensus_locked": True},
)

# Sentinel
empty = Signal.ZERO

# Content hash (SHA1)
h = sig.content_hash()

# Metrics as tuple (conf, contra, urgency, relevance)
v = sig.metrics_vector()
```

`Signal` is immutable. `flags` is stored as `MappingProxyType` — attempts to mutate it raise `TypeError`.

## Circuit

```python
@dataclass
class Circuit:
    nodes: dict[str, Node]              # {node_id: Node instance}
    wires: list[Wire]                   # All wire definitions
    sink_id: str                        # ID of the Sink node
    config: dict                        # {epsilon, max_iter}
    in_edges: dict[str, list[Wire]]     # {node_id: [incoming wires]}
    out_edges: dict[str, list[Wire]]    # {node_id: [outgoing wires]}
```

Typically created by `load_circuit()`, not constructed directly.

## Node (base class)

```python
from cirkit.nodes.base import Node
from cirkit.signal import Signal

class Node(ABC):
    def __init__(self, node_id: str, config: dict): ...

    @abstractmethod
    def step(self, inputs: dict[str, list[Signal]], state: dict) -> Signal: ...

    def _maybe_cached_step(self, inputs, state) -> Signal: ...
```

`inputs` is keyed by role: `{"context": [...], "peer": [...], "feedback": [...]}`. Each value is a list of `Signal` objects from that role's wires.

Subclass `Node` and implement `step()` to create a custom node type. See [Adding a Node Type](../guides/adding-nodes.md).

## Convenience import

```python
from cirkit import Circuit, Signal, load_circuit, run
```

All four names are exported from `cirkit/__init__.py`.
