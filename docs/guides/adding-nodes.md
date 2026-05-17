# Adding a Node Type

Custom node types are first-class — they use the same `Node` base class as all built-in types.

## Step 1 — Subclass Node

Create `cirkit/nodes/my_node.py`:

```python
from cirkit.nodes.base import Node
from cirkit.signal import Signal


class MyNode(Node):
    def __init__(self, node_id: str, config: dict):
        super().__init__(node_id, config)
        # Validate required config fields here, not in step()
        if "my_param" not in config:
            raise ValueError(f"MyNode {node_id}: 'my_param' is required")
        self.my_param = config["my_param"]

    def step(self, inputs: dict[str, list[Signal]], state: dict) -> Signal:
        # inputs is keyed by role: {"context": [...], "peer": [...], "feedback": [...]}
        context_signals = inputs.get("context", [])
        if not context_signals:
            return Signal.ZERO

        # Combine content from all context inputs
        combined = "\n".join(s.content for s in context_signals if s.content)

        # Do something with combined + self.my_param
        result = combined.upper()  # example transformation

        return Signal(
            content=result,
            confidence=0.9,
            contradiction=0.0,
            urgency=0.5,
            relevance=0.5,
        )
```

**Rules**:

- Return `Signal.ZERO` when there's nothing to output (no inputs, not ready).
- Validate required config fields in `__init__`, not in `step()` — this gives a clear error at load time.
- Do not mutate `inputs` or signals — they are immutable.
- Use `state` dict to persist data across iterations (e.g., cache a previous output).

## Step 2 — Register in NODE_REGISTRY

Add your node to `cirkit/nodes/__init__.py`:

```python
from cirkit.nodes.my_node import MyNode

NODE_REGISTRY["my_node"] = MyNode
```

The registry maps the JSON `"type"` string to the Python class.

## Step 3 — Use in a circuit

```json
{
  "id": "transform",
  "type": "my_node",
  "config": {"my_param": "value"}
}
```

```bash
python -m cirkit run my_circuit.json "input prompt"
```

## Overriding the cache (advanced)

By default, `_maybe_cached_step` in the base `Node` class:

- Filters `Signal.ZERO` from the cache key (C1 rule)
- Uses a single-slot cache (last input → last output)

If your node needs a different caching strategy — for example, a 64-entry LRU like `Motor` — override `_maybe_cached_step` entirely:

```python
def _maybe_cached_step(self, inputs, state):
    # Custom cache logic here
    return self.step(inputs, state)
```

Only override the cache if your node has the R2 contradiction bypass requirement (like Motor) or needs multi-entry caching.

## Adding config validation to circuit_utils.py

If your node requires specific config fields, add validation to `ui/circuit_utils.py` so the UI catches errors before running:

```python
# Inside validate_circuit(), in the per-node config check section:
if node["type"] == "my_node":
    if "my_param" not in cfg:
        errors.append(f"Node '{nid}': my_node requires 'my_param' in config")
```

This mirrors how Battery, AndGate, and Resistor validation is done.
