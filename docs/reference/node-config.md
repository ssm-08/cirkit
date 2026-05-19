# Node Config

Per-node `config` field reference for all built-in node types.

## Battery

```json
{
  "id": "task",
  "type": "battery",
  "config": {
    "content": "You are a senior engineer. Review the following:",
    "accumulate": false
  }
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `content` | string | **yes** | — | Fixed text emitted every iteration; prepended to the user prompt |
| `accumulate` | bool | no | `false` | If `true`, appends incoming feedback signals to the emitted content each iteration |

`content` is validated at load time — missing `content` raises `ValueError` immediately, not at runtime.

## Motor

```json
{
  "id": "writer",
  "type": "motor",
  "config": {
    "system": "You are a technical writer. End with {\"confidence\": 0.9}.",
    "model": "haiku"
  }
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `system` | string | **yes** | — | LLM system prompt; should include confidence instruction |
| `model` | string | no | CLI default | Model alias or full ID passed to `claude --model`. Use `"haiku"` for cheap low-stakes nodes; omit for Sonnet/Opus default |

**Confidence instruction**: Motor expects the LLM to output `{"confidence": X}` (0.0–1.0) as the last non-empty line. If absent, confidence is estimated via:

1. Fallback formula: `clamp(0.5 + 0.4 × tanh((len−200)/400), 0.1, 0.9)`
2. Hedge-phrase cap: if output contains hedging words ("actually", "wait", "let me reconsider", etc.), confidence capped at 0.5

## Resistor

```json
{
  "id": "filter",
  "type": "resistor",
  "config": {
    "threshold": 0.7
  }
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `threshold` | float | **yes** | — | Minimum confidence to pass; inputs below threshold become `Signal.ZERO` |

## AndGate

```json
{
  "id": "gate",
  "type": "and_gate",
  "config": {
    "threshold": 0.5,
    "merge_mode": "dedupe",
    "early_exit_threshold": 0.9
  }
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `threshold` | float | **yes** | — | Minimum confidence all non-ZERO inputs must meet to pass |
| `merge_mode` | string | no | `"concat"` | How to combine passing inputs: `concat` or `dedupe` |
| `early_exit_threshold` | float | no | `0.9` | If min(input confidence) ≥ this, sets `consensus_locked` flag for early circuit exit |

**merge_mode values**:

| Mode | Description |
|------|-------------|
| `concat` | Join content with `\n---\n` separator |
| `dedupe` | Line-level case-insensitive deduplication, preserve first-occurrence order |

When blocked (any input below `threshold`), the gate emits `contradiction = 1.0`. This is NOT `Signal.ZERO` — it triggers the R2 cache bypass in upstream Motors.

## Router

```json
{
  "id": "triage",
  "type": "router",
  "config": {
    "rule": "by_confidence",
    "branches": [
      {"branch": "high", "min_confidence": 0.8},
      {"branch": "medium", "min_confidence": 0.5},
      {"branch": "low", "default": true}
    ]
  }
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `rule` | string | **yes** | — | Dispatch rule: `by_confidence`, `by_content_length`, or `by_flag` |
| `branches` | array | **yes** | — | List of branch definitions |

**Branch fields by rule**:

| Rule | Required branch field | Description |
|------|----------------------|-------------|
| `by_confidence` | `min_confidence` | Route to first branch whose threshold the signal meets |
| `by_content_length` | `max_length` | Route to first branch whose length limit fits |
| `by_flag` | `flag_name` | Route to first branch whose flag is set on the signal |

Every branch list must contain exactly one entry with `"default": true` as fallback.

Router out-edges in the `wires` array use `branch` (the branch name string) instead of `role`. A wire must not have both `branch` and `role`.

## Sink

```json
{"id": "out", "type": "sink", "config": {}}
```

No config fields. The Sink accepts all incoming signals, selects the highest-confidence one (tie-break: `relevance`), and stores it as the circuit's final output.
