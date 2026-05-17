# CLI

## Entry point

After `pip install -e .`, the `cirkit` command is available. Alternatively, use `python -m cirkit` without installing.

## Commands

### `cirkit run`

```
cirkit run <circuit.json> "<prompt>"
```

Runs a circuit and streams iteration output to stdout.

| Argument | Description |
|----------|-------------|
| `circuit.json` | Path to the circuit JSON file |
| `<prompt>` | User prompt string; injected into all Battery nodes |

**Example**:

```bash
cirkit run examples/pr_review.json "Review this PR: adds retry logic to payment service"
```

**Windows note**: the prompt is passed via stdin to the `claude` subprocess, not via command-line arguments — this avoids PowerShell quoting issues with special characters.

## Output format

The CLI streams structured lines to stdout during execution:

```
[iter 0, delta=0.8231]
  [node writer: conf=0.82, contra=0.00, cached=False]
  [node reviewer: conf=0.78, contra=0.00, cached=False]
  [node gate: conf=0.80, contra=0.00, cached=False]
  [node synthesizer: conf=0.85, contra=0.00, cached=False]
[iter 1, delta=0.0312]
  [node writer: conf=0.89, contra=0.00, cached=True]
  ...
[converged after 2 iter, delta=0.0312]

=== OUTPUT ===
<final circuit output>
```

| Line pattern | Meaning |
|-------------|---------|
| `[iter N, delta=X]` | Iteration N completed; aggregate delta is X |
| `[node ID: conf=X, contra=Y, cached=Z]` | Per-node status for this iteration |
| `[converged after N iter, delta=X]` | Circuit converged before max_iter |
| `[MAX_ITER reached after N iter, delta=X]` | max_iter hit without convergence |
| `=== OUTPUT ===` | Separator before final output text |

The `ui/server.py` and `ui/views.py` parse this output via `circuit_utils.parse_cirkit_line()` and convert it to ndjson events for the browser.

## Error handling

| Situation | Exit code | Output |
|-----------|-----------|--------|
| Circuit file not found | 1 | Error message to stderr |
| Invalid circuit JSON | 1 | Validation errors to stderr |
| `claude` CLI not installed | 1 | `LLMError: command not found` to stderr |
| Motor LLM timeout | 0 | Motor returns `Signal.ZERO`; run continues |
| max_iter reached | 0 | Prints `[MAX_ITER reached ...]`; outputs last Sink content |

Motor errors (LLM call failures) are non-fatal — the motor emits `Signal.ZERO` and logs to stderr. The circuit continues running.

## `python -m cirkit` vs `cirkit`

Both are equivalent. `python -m cirkit` works without `pip install -e .` — it runs `cirkit/__main__.py` directly. The `cirkit` entry point is installed by setuptools and does the same thing.
