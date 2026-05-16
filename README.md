# CirKit

A signal circuit reasoning engine. You define a graph of typed nodes in JSON. Signals propagate through the graph until the system converges (Δ < ε). The LLM is one node type — not the orchestrator. Stopping is computed, not configured.

---

## The core idea

Most LLM orchestration frameworks make the agent the orchestrator: you write Python that calls LLMs, retries, merges, and decides when to stop. CirKit inverts this. The **topology is the orchestrator**. Retry logic, escalation, consensus, and termination are first-class primitives expressed as nodes and wires — no imperative glue code.

```
Battery → Motor → Resistor → AND Gate → Sink
                    ↑                      |
                    └──── feedback ────────┘
```

The engine runs iterations. Each iteration: every node reads the previous snapshot, computes its output, and emits a Signal. The engine measures aggregate signal delta. When delta < ε, the circuit has converged. The Sink's last received signal is the output.

---

## Install

```powershell
# Clone and install (editable)
pip install -e .

# Or run directly without installing
python -m cirkit run <circuit.json> "<prompt>"
```

Requires Python 3.11+. No API keys. LLM access uses the local `claude -p` CLI (must be on PATH and logged in).

---

## Quick start

**hello.json**
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
```

Output:
```
[converged after 2 iter, final delta=0.0000]
Paris.
```

---

## How it works

### Signal

The fundamental unit. Frozen dataclass with:

| Field | Type | Meaning |
|---|---|---|
| `content` | str | The payload |
| `confidence` | float [0,1] | How sure the node is this signal should advance |
| `contradiction` | float [0,1] | How contradicted/rejected this signal is |
| `urgency` | float [0,1] | Time-sensitivity |
| `relevance` | float [0,1] | How relevant to the task |
| `flags` | dict | Engine-control metadata (`consensus_locked`, `needs_synthesis`) |

`Signal.ZERO` is the sentinel for "no signal yet." Every node handles it gracefully.

### Engine loop (Jacobi update)

```
1. Initialize all outputs to Signal.ZERO
2. Inject user_prompt into Battery nodes
3. Bootstrap: run input-less nodes once (Battery seeds before iter 0)
4. For each iteration:
   a. Freeze prev_outputs snapshot
   b. Each node reads prev_outputs, computes new output
   c. Compute aggregate delta = mean(0.6*metric_dist + 0.4*content_change) across all nodes
   d. If delta < epsilon → converged, break
   e. If any signal has consensus_locked=True AND Sink has real content → break early (R4)
5. Return Sink's last_input as final output
```

**Why Jacobi (synchronous) update:** cyclic graphs work safely. A feedback edge means downstream output appears one iteration later as upstream input — exactly the discrete-time behavior CirKit wants.

**Propagation cost:** signal moves 1 hop per iteration. A chain `A → B → C → D` needs ≥3 iterations for A's content to reach D.

### Convergence math

```
delta(prev, curr) = 0.6 * metric_dist + 0.4 * content_change

  metric_dist   = euclidean(prev.metrics, curr.metrics) / 2.0   # normalized [0,1]
  content_change = 0.0 if sha1(prev.content) == sha1(curr.content) else 1.0

aggregate_delta = mean(delta(n) for all nodes n)
```

Metrics weighted 60%, content 40% — Motor's slight prose drift doesn't block convergence once inputs stabilize. Motor caches `input_hash → output` so content_change hits 0 when inputs stabilize.

### Wire roles

Every wire carries a semantic role:

| Role | Meaning | Motor section |
|---|---|---|
| `context` | Upstream context (default) | `[CONTEXT]` |
| `feedback` | Downstream rejection / critique | `[FEEDBACK FROM PREVIOUS ITERATION]` |
| `peer` | Sibling output at same stage | `[PEER OUTPUTS]` |

Motor knows which input is a reviewer's rejection vs. the original task.

---

## Node types

### Battery
Authoritative source. Emits `config.content + user_prompt` with `confidence=1.0` every iteration.

```json
{ "id": "ctx", "type": "battery", "config": { "content": "Do the task.", "accumulate": false } }
```

`accumulate: true` — appends incoming `feedback` signals to the emission across iterations.

---

### Motor
LLM-backed reasoning node. Calls `claude -p` via subprocess.

```json
{ "id": "agent", "type": "motor", "config": { "system": "You are a code reviewer." } }
```

Every Motor automatically gets a fixed prefix prepended (defines confidence semantics, single-pass rules, required JSON footer). User's `system` field appends after `YOUR TASK:`.

**Motor's final line must be:** `{"confidence": 0.X}`

**Cache (R12):** Motor caches `input_hash → output`. Same inputs → cache hit → no LLM call → delta=0.

**Cache bypass (R2):** If any input has `contradiction >= 0.8`, cache is skipped and a fresh LLM call is made. High contradiction = rejection signal — returning the cached rejected answer would be wrong.

**On error:** Returns `Signal.ZERO`, logs to stderr. Never raises.

---

### Resistor
Threshold gate. Single input.

```json
{ "id": "filter", "type": "resistor", "config": { "threshold": 0.55 } }
```

- `confidence >= threshold` → pass through unchanged
- `confidence < threshold` → return `Signal.ZERO`

No attenuation. Binary pass/block.

---

### AND Gate
Multi-input consensus gate.

```json
{
  "id": "gate",
  "type": "and_gate",
  "config": {
    "threshold": 0.55,
    "early_exit_threshold": 0.9,
    "merge_mode": "concat"
  }
}
```

**Pass condition:** ALL non-ZERO inputs have `confidence >= threshold`.

**If passing:** merges content by `merge_mode`:

| Mode | LLM? | When to use |
|---|---|---|
| `concat` (default) | No | Complementary specialists (writer + security). Joins with `\n---\n`. |
| `dedupe` | No | Parallel samples doing same job. Line-level dedup, first-occurrence order. |
| `synthesize` | Yes (downstream) | Disagreeing inputs. Sets `flags["needs_synthesis"]=True`. Wire to a synthesizer Motor. |

**Metrics:** per-channel MIN across all passing inputs.

**If blocked:** returns `Signal(confidence=0.0, contradiction=1.0)` — NOT `Signal.ZERO`. The `contradiction=1.0` triggers Motor cache bypass upstream, forcing a fresh LLM call.

**Early exit (R4):** if passing AND `min_confidence >= early_exit_threshold`, sets `flags["consensus_locked"]=True`. Engine breaks early once the answer is clearly settled (and Sink has real content).

---

### Sink
Terminal node. Records highest-confidence incoming signal. Always returns `Signal.ZERO`.

```json
{ "id": "out", "type": "sink", "config": {} }
```

Stores selection in `state["last_input"]`. Engine reads this after the loop. No out-edges allowed.

---

### Router
Adaptive-compute branching. One input, N named branch outputs.

```json
{
  "id": "router",
  "type": "router",
  "config": {
    "rule": "by_confidence",
    "branches": [
      { "branch": "fast", "min_confidence": 0.85 },
      { "branch": "slow", "default": true }
    ]
  }
}
```

Supported rules: `by_confidence`, `by_content_length`, `by_flag`. First matching branch wins; exactly one branch must have `"default": true`.

Router-originating wires use `branch` field instead of `role`:
```json
{ "from": "router", "to": "fast_motor", "branch": "fast" }
```

**Triage pattern:** put a cheap classifier Motor before the Router. Trivial prompts skip the full review pipeline (2 LLM calls vs. 12–20).

---

## JSON circuit schema

```json
{
  "config": { "epsilon": 0.05, "max_iter": 10 },
  "sink": "<sink-node-id>",
  "nodes": [
    { "id": "<id>", "type": "<type>", "config": { ... } }
  ],
  "wires": [
    { "from": "<id>", "to": "<id>", "role": "context" }
  ]
}
```

**Validation on load:**
- `epsilon` ∈ (0, 1.0], `max_iter` ≥ 1
- `sink` must reference a node of type `sink`
- All wire endpoints must exist
- No duplicate node IDs
- Sink has no out-edges
- Self-loops allowed
- Wire `role` ∈ `{context, feedback, peer}` (default `context`)
- Router wires: `branch` field required; `role` forbidden
- Non-Router wires: `branch` forbidden

---

## Example: PR review circuit

`examples/pr_review.json` — two parallel reviewers + consensus + synthesizer:

```
Battery (ctx) ──context──► Writer Motor ──context──► Resistor (filter)
           │                                                   │ peer
           └──context──► Security Motor ─────────────────────►│
                              ▲                          AND Gate (gate)
                              │ feedback                       │ context
                              └───────────────────────────────►│
                                                         Synthesizer Motor
                                                               │ context
                                                             Sink (out)
```

Expected behavior:
- Iter 0: Battery seeds; writer + security run independently
- Iter 1: filter passes/zeros writer; AND-Gate either passes or blocks
- Iter 2 (on block): AND-Gate's `contradiction=1.0` reaches writer + security → R2 bypass → they revise
- Iter 3–4: consensus reached, `consensus_locked=True`; synthesizer fuses both reviews; engine exits early
- Output: synthesizer's coherent fused report

```powershell
python -m cirkit run examples\pr_review.json "Refactored auth.py to use bcrypt instead of MD5. Updated 12 tests."
```

---

## File structure

```
cirkit/
├── __init__.py          # Public API: Circuit, Signal, run, load_circuit
├── __main__.py          # CLI entry point
├── signal.py            # Signal dataclass + ZERO sentinel
├── convergence.py       # delta() + aggregate_delta()
├── graph.py             # Circuit, Wire, load_circuit() with full JSON validation
├── engine.py            # Synchronous Jacobi update loop
├── state.py             # RunState, RunResult
├── llm.py               # call_claude() subprocess wrapper
├── confidence.py        # Trailing-JSON parser + heuristic fallback + hedge cap
└── nodes/
    ├── __init__.py      # NODE_REGISTRY (type string → class)
    ├── base.py          # Node ABC + _maybe_cached_step (R12 lazy cache)
    ├── battery.py
    ├── sink.py
    ├── resistor.py
    ├── and_gate.py
    ├── router.py
    └── motor.py         # LLM node; overrides _maybe_cached_step with R2 bypass

tests/
├── test_signal.py
├── test_convergence.py
├── test_nodes.py
├── test_wire_roles.py
├── test_and_gate_modes.py
├── test_router.py
├── test_motor_cache.py
├── test_engine_no_motor.py     ← core thesis proof
├── test_early_exit.py
├── test_engine_oscillation.py
└── test_engine_mock_motor.py

examples/
└── pr_review.json
```

---

## Testing

```powershell
# Full suite (92 tests, <1s, zero LLM calls)
python -m pytest tests/ -v

# Core thesis: engine works with no Motor nodes
python -m pytest tests/test_engine_no_motor.py -v
```

The no-Motor test is the falsifiable proof that CirKit is not an LLM wrapper.

---

## Adding a node type

1. Create `cirkit/nodes/<name>.py`, subclass `Node`:
   ```python
   from cirkit.nodes.base import Node
   from cirkit.signal import Signal

   class MyNode(Node):
       def __init__(self, config: dict):
           self.config = config

       def step(self, inputs: dict[str, list[Signal]], state: dict) -> Signal:
           # inputs keys: "context", "feedback", "peer"
           # state persists across iterations
           # always return Signal, never None
           ...
   ```

2. Register in `cirkit/nodes/__init__.py`:
   ```python
   from cirkit.nodes.mynode import MyNode
   NODE_REGISTRY["my_node"] = MyNode
   ```

3. `_maybe_cached_step` in `base.py` handles R12 lazy caching automatically. Override it only if your node needs contradiction-bypass logic (like Motor).

---

## Output format

```
[converged after N iter, final delta=0.XXXX]
<sink content>
```

Non-convergent:
```
[MAX_ITER (non-convergent) after N iter, final delta=0.XXXX]
<last signal that reached Sink>
```

Non-convergence is reported, never raised.
