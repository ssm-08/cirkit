# CirKit

[![CI](https://github.com/ssm-08/cirkit/actions/workflows/ci.yml/badge.svg)](https://github.com/ssm-08/cirkit/actions/workflows/ci.yml)

Signal circuit reasoning engine. Define a graph of nodes in JSON — signals flow through it until outputs converge. The LLM is one node type, not the orchestrator.

**[Full documentation →](https://ssm-08.github.io/cirkit/)**

---

## The problem

Most LLM frameworks are imperative: you write Python that calls models, inspects results, decides what to retry, and knows when to stop. As pipelines grow, you end up with ad-hoc orchestration logic spread across your codebase.

CirKit is declarative. Describe the **topology** — which nodes exist and how they're wired — and the engine handles iteration, retry, and termination automatically. Changing a pipeline means editing JSON, not refactoring code.

**Convergence instead of a fixed step count.** The engine runs iterations until signal delta < ε. When nothing is changing, the system has settled. You set ε and `max_iter`; the engine stops itself.

**Signals travel one hop per iteration.** A four-node chain `A → B → C → D` needs at least 3 iterations for A's output to reach D. This is deterministic and inspectable — not a black box.

---

## Prerequisites

- Python 3.11+
- `claude` CLI installed and authenticated (`claude auth login`) — for circuits with Motor nodes
- No API keys required — CirKit shells out to the local `claude` CLI

---

## Install

```powershell
pip install -e .
# or run without installing:
python -m cirkit run <circuit.json> "<prompt>"
```

---

## Quick start

```json
{
  "config": { "epsilon": 0.05, "max_iter": 3 },
  "sink": "out",
  "nodes": [
    { "id": "ctx",   "type": "battery", "config": { "content": "Answer concisely." } },
    { "id": "agent", "type": "motor",   "config": { "system": "You are a helpful assistant." } },
    { "id": "out",   "type": "sink",    "config": {} }
  ],
  "wires": [
    { "from": "ctx",   "to": "agent" },
    { "from": "agent", "to": "out"   }
  ]
}
```

```powershell
python -m cirkit run hello.json "What is the capital of France?"
# [converged after 2 iter, final delta=0.0000]
# Paris.
```

---

## Node types

| Type | Role |
|------|------|
| `battery` | Static signal source — emits fixed content + user prompt every iteration |
| `motor` | LLM call — assembles prompt from inputs, extracts confidence from output |
| `resistor` | Single-input threshold filter — passes signal only if confidence ≥ threshold |
| `and_gate` | Consensus gate — passes when ALL inputs exceed threshold; merges content |
| `router` | Content-based dispatcher — routes signal to one of N named branches |
| `sink` | Terminal collector — selects highest-confidence input as circuit output |

**Wire roles** tell a receiving Motor what each signal means:

| Role | Framing in prompt | Use for |
|------|-------------------|---------|
| `context` | `[CONTEXT]` | Upstream input — battery→motor, motor→gate, gate→sink |
| `peer` | `[PEER OUTPUTS]` | Sibling Motor sharing results at the same stage |
| `feedback` | `[FEEDBACK FROM PREVIOUS ITERATION]` | Back-edge — downstream result looping upstream |

---

## Circuit design patterns

**Linear pipeline** — for generation tasks. Converges in 1–2 iterations, no feedback needed.

```
battery → drafter → formatter → sink
```

Example: `examples/resume_html.json`

---

**Parallel reviewers + consensus** — for critique tasks. Multiple independent reviewers must agree before output advances.

```
battery ──► reviewer_A ──► AND-gate ──► sink
        └──► reviewer_B ──►    │
                 ▲              │
                 └── feedback ──┘
```

When the gate blocks, it emits the real merged content with `contradiction=1.0` — motors receive this as feedback and refine against it. Example: `examples/pr_review.json`

---

**Triage** — cheap classifier routes easy inputs to a fast path, hard inputs through the full pipeline.

```
battery → classifier → router → [fast path]
                               → [slow path]
```

---

## UI

A visual circuit builder is included — single HTML file, no build step.

```powershell
python ui/server.py        # http://localhost:8080/
python ui/server.py 9000   # custom port
```

Drag nodes from the palette, draw wires between ports, inspect and configure via the side panel. RUN streams live iteration events from the engine. Demo mode works with no backend.

**Django integration:** `ui/views.py` + `ui/urls.py` — mount at `/cirkit/` for production use.

---

## Testing

```powershell
python -m pytest tests/ -v                         # 135 tests, <1s, no LLM calls
python -m pytest tests/test_engine_no_motor.py -v  # core thesis: engine works without Motor
```

---

## Current limitations

**1-iteration lag on all wires.** Every wire carries the previous iteration's output. A motor with a peer or feedback wire sees `Signal.ZERO` on iteration 1 (sibling had no output yet). Real content arrives starting iteration 2. This is by design — it makes the Jacobi update fully deterministic.

**Feedback loops need higher epsilon.** LLMs produce slightly different text on every call even with identical prompts. With `epsilon: 0.05`, content drift alone (≈0.1 per cache-miss node) can exceed the threshold when multiple motors are active. Use `epsilon: 0.15` for any circuit with feedback wires.

**Motor requires `claude` CLI on PATH.** No direct API integration yet — CirKit shells out to the local `claude -p` subprocess. Authentication uses your existing Claude Code session (`claude auth login`).

**Windows terminal encoding.** Windows PowerShell defaults to CP1252. Avoid non-ASCII characters in Battery `content` strings or Motor system prompts if you see encoding errors. Set `PYTHONIOENCODING=utf-8` if needed.

---

## File structure

```
cirkit/
├── signal.py         # Signal dataclass + ZERO sentinel
├── convergence.py    # delta() + aggregate_delta()
├── graph.py          # Circuit, Wire, load_circuit() with JSON validation
├── engine.py         # Synchronous Jacobi update loop
├── state.py          # RunState, RunResult
├── llm.py            # call_claude() subprocess wrapper
├── confidence.py     # Trailing-JSON parser + heuristic fallback
└── nodes/            # Battery, Motor, Resistor, AndGate, Router, Sink

tests/                # 135 unit tests
examples/
├── pr_review.json    # Parallel reviewers + consensus gate + feedback
└── resume_html.json  # Linear pipeline: drafter → HTML formatter
ui/
├── index.html        # Visual circuit builder (standalone)
├── server.py         # stdlib dev server
├── circuit_utils.py  # validate_circuit() + parse_cirkit_line()
├── views.py          # Django views (StreamingHttpResponse)
└── urls.py           # Django URL config
```

---

## Docs

Full documentation, architecture diagrams, and reference:

**[ssm-08.github.io/cirkit](https://ssm-08.github.io/cirkit)**

- [Quickstart](https://ssm-08.github.io/cirkit/guides/quickstart/) — step-by-step setup
- [Circuit design patterns](https://ssm-08.github.io/cirkit/guides/circuit-design/) — topologies, pitfalls, tuning
- [Node config reference](https://ssm-08.github.io/cirkit/reference/node-config/) — all config fields
- [JSON schema](https://ssm-08.github.io/cirkit/reference/json-schema/) — full circuit format
- [Architecture](https://ssm-08.github.io/cirkit/reference/architecture/) — engine internals and data flow
