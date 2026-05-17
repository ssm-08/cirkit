# Quickstart

## Prerequisites

- Python 3.11+
- `claude` CLI installed and authenticated (for circuits with Motor nodes)

## Install

```bash
git clone <repo>
cd cirkit
pip install -e .
```

This installs the `cirkit` CLI entry point. You can also run `python -m cirkit` without installing.

## Run the example circuit

```bash
python -m cirkit run examples/pr_review.json "Review this change: adds retry logic to payment service"
```

You'll see iteration output streaming to stdout:

```
[iter 0, delta=0.8231]
  [node writer: conf=0.82, contra=0.00, cached=False]
  [node reviewer: conf=0.78, contra=0.00, cached=False]
  [node gate: conf=0.80, contra=0.00, cached=False]
  [node synthesizer: conf=0.85, contra=0.00, cached=False]
[iter 1, delta=0.0312]
  ...
[converged after 2 iter, delta=0.0312]

=== OUTPUT ===
The PR adds retry logic with exponential backoff to the payment service...
```

## Run a linear pipeline

```bash
python -m cirkit run examples/resume_html.json "Software engineer with 5 years Python experience"
```

Linear circuits (no feedback loop) typically converge in 1–2 iterations.

## Launch the UI canvas

```bash
python ui/server.py
# → Serving at http://localhost:8080/
```

Open `http://localhost:8080` in your browser. The canvas works in demo mode (4-iteration simulation) even without the backend running — it auto-detects the server.

To use a custom port:

```bash
python ui/server.py 9000
```

## Build a minimal circuit

Create `my_circuit.json`:

```json
{
  "config": {"epsilon": 0.05, "max_iter": 3},
  "sink": "out",
  "nodes": [
    {
      "id": "task",
      "type": "battery",
      "config": {"content": "Summarize the following in one paragraph:"}
    },
    {
      "id": "summarizer",
      "type": "motor",
      "config": {
        "system": "You are a concise technical writer. Output a single paragraph. End with {\"confidence\": 0.9}."
      }
    },
    {"id": "out", "type": "sink", "config": {}}
  ],
  "wires": [
    {"from": "task", "to": "summarizer", "role": "context"},
    {"from": "summarizer", "to": "out", "role": "context"}
  ]
}
```

```bash
python -m cirkit run my_circuit.json "The Jacobi method is an iterative algorithm..."
```

## Next steps

- [Circuit Design Patterns](circuit-design.md) — topologies, pitfalls, tuning
- [Nodes reference](../concepts/nodes.md) — all node types and their config
- [JSON Schema](../reference/json-schema.md) — full circuit format
