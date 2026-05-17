# Engine Loop

The CirKit engine runs a **synchronous Jacobi iteration** — every node reads the _previous_ round's outputs before any node writes its new output. This prevents ordering artifacts and makes circuits deterministic regardless of node evaluation order.

## Phases

### Phase A — Initialize

All node outputs start as `Signal.ZERO`. A `RunState` object is created to track outputs, per-node state dicts, and delta history.

### Phase B — Inject user prompt

The engine injects the user prompt string into every Battery node's state dict (`state["user_prompt"]`). This happens before any iteration runs.

### Phase C — R9 Bootstrap

Nodes with no in-edges (typically Batteries) are run once before iteration 0. This seeds their outputs so downstream nodes see real content on the first iteration rather than ZERO.

### Phase D — Main loop

For each iteration from 0 to `max_iter − 1`:

1. **Snapshot**: copy all current outputs as `prev_outputs`
2. **Step each node**: call `_maybe_cached_step(inputs_from_prev, state)` on every node
3. **Compute delta**: `aggregate_delta(prev_outputs, curr_outputs)` — mean across all nodes
4. **Check convergence (R10)**: if `delta < epsilon`, exit with `converged = True`
5. **Check early exit (R4/G14)**: if `consensus_locked` flag is set AND the Sink has received positive-confidence content, exit early
6. **Fire callback**: `on_iter(iteration, outputs, delta)` if provided

### Phase E — Extract output

The Sink node's `state["last_input"]` is returned as the circuit's final output in a `RunResult`.

## RunResult

```python
@dataclass
class RunResult:
    output: Signal        # Sink's selected signal
    iterations: int       # How many iterations ran
    converged: bool       # True if delta < epsilon before max_iter
    delta_history: list   # Per-iteration aggregate delta values
    all_outputs: dict     # Final outputs keyed by node id
```

## Non-convergence

If `max_iter` is reached without `delta < epsilon`, the engine returns normally with `converged = False` — no exception is raised. The output is whatever the Sink last collected.

Non-convergence in feedback-loop circuits usually means the motors are still debating. Options:

- Increase `max_iter`
- Lower the AND-Gate `threshold` (0.45–0.55 is the sweet spot)
- Check that Motor system prompts rate confidence on completeness, not on outcome

## Callback

Pass `on_iter` to `run()` to receive live iteration events:

```python
def on_iter(iteration: int, outputs: dict[str, Signal], delta: float):
    print(f"iter {iteration}, delta={delta:.4f}")

result = run(circuit, "my prompt", on_iter=on_iter)
```

The CLI and UI dev server use this callback to stream `[iter N, delta=X]` and per-node status lines to stdout and the browser respectively.
