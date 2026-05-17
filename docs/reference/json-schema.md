# JSON Schema

A CirKit circuit is a single JSON object with four top-level keys.

## Top-level structure

```json
{
  "config": { "epsilon": 0.05, "max_iter": 5 },
  "sink": "output_node_id",
  "nodes": [ ... ],
  "wires": [ ... ]
}
```

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `config` | object | yes | Convergence parameters |
| `sink` | string | yes | ID of the terminal Sink node |
| `nodes` | array | yes | Node definitions |
| `wires` | array | yes | Edge definitions |

## config

```json
"config": {
  "epsilon": 0.05,
  "max_iter": 5
}
```

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `epsilon` | float | `(0, 1.0]` | Convergence threshold; loop exits when `aggregate_delta < epsilon` |
| `max_iter` | int | `≥ 1` | Safety-net iteration cap |

## nodes

Each element is a node definition:

```json
{
  "id": "my_node",
  "type": "battery",
  "config": { ... }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Unique node identifier; referenced by `sink` and `wires` |
| `type` | string | yes | Node type (see valid values below) |
| `config` | object | yes | Node-specific configuration |

**Valid `type` values**: `battery`, `motor`, `resistor`, `and_gate`, `router`, `sink`

Node IDs must be unique across the entire circuit. The node referenced by `sink` must have `type: sink` and must have no out-edges.

## wires

Each element is a directed edge:

```json
{"from": "source_id", "to": "target_id", "role": "context"}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `from` | string | yes | Source node ID |
| `to` | string | yes | Target node ID |
| `role` | string | yes (non-Router) | `context`, `peer`, or `feedback` |
| `branch` | string | yes (Router out-edges) | Branch name declared in the Router's config |

**Valid `role` values**: `context` (default), `peer`, `feedback`

Router out-edges use `branch` instead of `role`. A wire must not have both `branch` and `role`.

Non-feedback wires must not form cycles. Wires with `role: feedback` are exempt from cycle detection.

## Complete example

```json
{
  "config": {"epsilon": 0.05, "max_iter": 5},
  "sink": "out",
  "nodes": [
    {
      "id": "task",
      "type": "battery",
      "config": {
        "content": "You are a senior engineer. Review the following PR:"
      }
    },
    {
      "id": "writer",
      "type": "motor",
      "config": {
        "system": "Draft a review. Rate confidence as JSON on the last line: {\"confidence\": 0.9}."
      }
    },
    {
      "id": "reviewer",
      "type": "motor",
      "config": {
        "system": "Critique the draft review. Rate confidence on thoroughness. End with {\"confidence\": 0.85}."
      }
    },
    {
      "id": "gate",
      "type": "and_gate",
      "config": {"threshold": 0.5, "merge_mode": "synthesize"}
    },
    {
      "id": "synthesizer",
      "type": "motor",
      "config": {
        "system": "Synthesize both inputs into one final review. End with {\"confidence\": 0.95}."
      }
    },
    {"id": "out", "type": "sink", "config": {}}
  ],
  "wires": [
    {"from": "task",        "to": "writer",      "role": "context"},
    {"from": "task",        "to": "reviewer",    "role": "context"},
    {"from": "writer",      "to": "reviewer",    "role": "peer"},
    {"from": "writer",      "to": "gate",        "role": "peer"},
    {"from": "reviewer",    "to": "gate",        "role": "peer"},
    {"from": "gate",        "to": "synthesizer", "role": "context"},
    {"from": "synthesizer", "to": "out",         "role": "context"},
    {"from": "synthesizer", "to": "writer",      "role": "feedback"},
    {"from": "synthesizer", "to": "reviewer",    "role": "feedback"}
  ]
}
```

## Validation errors

The engine and UI validate circuits at load time. Common errors:

| Error | Cause |
|-------|-------|
| `'epsilon' must be in (0, 1.0]` | `epsilon: 0` or `epsilon: 1.5` |
| `Node 'X': unknown type 'Y'` | Typo in `type` field |
| `'sink' node 'X' has out-edges` | Sink node has wires going out |
| `Node 'X': battery requires 'content'` | Battery config missing `content` |
| `Node 'X': and_gate requires 'threshold'` | AND-Gate config missing `threshold` |
| `Cycle detected: X → Y → X` | Non-feedback cycle in graph |
| `Router wire must use 'branch', not 'role'` | Router out-edge has `role` instead of `branch` |
