# CirKit

[![CI](https://github.com/ssm-08/cirkit/actions/workflows/ci.yml/badge.svg)](https://github.com/ssm-08/cirkit/actions/workflows/ci.yml)

A signal circuit reasoning engine. Define a graph of nodes in JSON. Signals flow through the graph until outputs stop changing. The LLM is one node type — not the orchestrator.

**[Documentation](https://ssm-08.github.io/cirkit/)**

---

## The core idea

Most LLM frameworks are imperative: you write Python that calls LLMs, decides what to do with results, retries, and knows when to stop. CirKit is declarative: describe the **topology** (which nodes exist, how they're wired) and the engine handles iteration, retry, and termination automatically.

**Convergence instead of a fixed step count.** The engine runs iterations until signal delta < ε. Delta measures how much outputs changed since the last iteration. When nothing is changing, the system has settled. You set ε and max_iter; the engine stops itself.

**Propagation cost.** Signals travel one hop per iteration. A four-node chain `A → B → C → D` needs at least 3 iterations for A's output to reach D.

---

## Install

```powershell
pip install -e .
# or skip install entirely:
python -m cirkit run <circuit.json> "<prompt>"
```

Requires Python 3.11+. No API keys. Uses the local `claude -p` CLI (must be on PATH and logged in).

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

## UI

A visual circuit builder is included — single HTML file, no build step.

```powershell
python ui/server.py        # http://localhost:8080/
python ui/server.py 9000   # custom port
```

Drag nodes from the palette, draw wires between ports, inspect and configure via the side panel. RUN streams live iteration events from the engine. Demo mode works with no backend.

**Django integration:** `ui/views.py` + `ui/urls.py` — mount at `/cirkit/` for production use.

---

## How it works

**Signals** are the unit of data flowing between nodes — frozen structs with `content`, `confidence`, `contradiction`, `urgency`, and `relevance`. `Signal.ZERO` means "nothing yet."

**Wire roles** tell the receiving node why it's getting a signal:
- `context` — normal upstream input (default)
- `peer` — sibling at the same stage sharing results
- `feedback` — downstream result looping back upstream (the only legal cycle)

**Node types:** `battery` (static source), `motor` (LLM call), `resistor` (threshold filter), `and_gate` (consensus gate), `router` (branch on rule), `sink` (terminal collector).

**Engine loop:**
1. Initialize all outputs to `Signal.ZERO`
2. Inject `user_prompt` into Battery nodes
3. Run input-less nodes once (bootstrap)
4. Each iteration: every node reads the previous iteration's snapshot and computes a new output (synchronous Jacobi update — cycles are safe)
5. `aggregate_delta < epsilon` → converged; `consensus_locked` + Sink has content → early exit

---

## Circuit design patterns

**Linear pipeline** — for generation tasks. Converges in 1–2 iterations, no feedback needed.
```
battery → drafter → formatter → sink
```
Example: `examples/resume_html.json`

**Parallel reviewers + consensus** — for critique tasks. Multiple independent reviewers must agree before output advances.
```
battery ──► reviewer_A ──► AND-gate ──► synthesizer ──► sink
        └──► reviewer_B ──►                  │
                 ▲                            │
                 └────── feedback ────────────┘
```
Feedback flows from the synthesizer (not the gate — a blocked gate sends `[BLOCKED]`, which is useless). Example: `examples/pr_review.json`

**Triage** — cheap classifier routes easy inputs through a fast path, hard inputs through the full pipeline.
```
battery → classifier → router → [fast path]
                               → [slow path]
```

---

## Testing

```powershell
python -m pytest tests/ -v                         # 118 tests, <1s, no LLM calls
python -m pytest tests/test_engine_no_motor.py -v  # core thesis: engine works without Motor
```

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

tests/                # 118 unit tests
examples/
├── pr_review.json    # Parallel reviewers + consensus + synthesizer
└── resume_html.json  # Linear pipeline: drafter → HTML formatter
ui/
├── index.html        # Visual circuit builder (standalone)
├── server.py         # stdlib dev server
├── circuit_utils.py  # validate_circuit() + parse_cirkit_line()
├── views.py          # Django views (StreamingHttpResponse)
└── urls.py           # Django URL config
```
