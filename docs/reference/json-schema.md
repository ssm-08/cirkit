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

The `examples/pr_review.json` circuit — two independent reviewers, consensus gate, gate feedback:

```json
{
  "config": {"epsilon": 0.05, "max_iter": 5},
  "sink": "out",
  "nodes": [
    {
      "id": "ctx",
      "type": "battery",
      "config": {
        "content": "Review the following pull request. Identify bugs, security risks, and quality issues."
      }
    },
    {
      "id": "writer",
      "type": "motor",
      "config": {
        "system": "Produce a code-review report. Focus on correctness, logic, and code quality. Rate your confidence 0.0-1.0 based on how thorough and certain you are."
      }
    },
    {
      "id": "security",
      "type": "motor",
      "config": {
        "system": "Audit the PR for security vulnerabilities. Rate confidence 0.0-1.0 on completeness of review, not on whether issues were found."
      }
    },
    {
      "id": "gate",
      "type": "and_gate",
      "config": {"threshold": 0.5, "early_exit_threshold": 0.9, "merge_mode": "dedupe"}
    },
    {"id": "out", "type": "sink", "config": {}}
  ],
  "wires": [
    {"from": "ctx",      "to": "writer",   "role": "context"},
    {"from": "ctx",      "to": "security", "role": "context"},
    {"from": "writer",   "to": "gate",     "role": "context"},
    {"from": "security", "to": "gate",     "role": "context"},
    {"from": "gate",     "to": "out",      "role": "context"},
    {"from": "gate",     "to": "writer",   "role": "feedback"},
    {"from": "gate",     "to": "security", "role": "feedback"}
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
