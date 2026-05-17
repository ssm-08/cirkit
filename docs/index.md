# CirKit

**Signal circuit reasoning engine.** Define a graph of nodes in JSON; signals flow through it until outputs converge. The LLM is one node type — the circuit is the orchestration.

```
Battery ──context──► Motor (writer)   ──peer──► AND-Gate ──► Synthesizer ──► Sink
                  ► Motor (reviewer) ──peer──►               │
                  ◄──────────────── feedback ◄───────────────┘
```

Signals carry `content`, `confidence`, `contradiction`, and other metrics. Every iteration, each node reads the previous round's outputs and produces a new signal. The loop runs until `Δ < ε` — convergence — or `max_iter` is reached.

## Why CirKit

- **Declarative**: circuits are JSON files, not code. Change topology without touching Python.
- **LLM-agnostic**: the engine calls `claude -p` via subprocess; swap any CLI-accessible model with no code changes.
- **Reproducible**: same circuit + same prompt produces the same output (Motor caches by input content hash).

## Quick start

```bash
pip install -e .
python -m cirkit run examples/pr_review.json "Review this PR: adds retry logic to payment service"
```

Or launch the visual canvas:

```bash
python ui/server.py    # → http://localhost:8080
```

→ [Full quickstart guide](guides/quickstart.md)
