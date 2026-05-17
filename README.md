# CirKit

A signal circuit reasoning engine. You define a graph of nodes in JSON. Signals flow through the graph until outputs stop changing. The LLM is one node type — not the orchestrator.

---

## The core idea

Most LLM frameworks are imperative: you write Python that calls LLMs, decides what to do with results, retries, and knows when to stop. CirKit is declarative: you describe the **topology** (which nodes exist, how they're wired) and the engine figures out iteration, retry, and termination automatically.

**Why this matters:** you can express "two reviewers must agree before output advances" or "if confidence drops, loop back and revise" purely in JSON — no Python glue.

**Convergence instead of a fixed step count:** the engine runs iterations until signal delta < ε. Delta measures how much outputs changed since the last iteration (60% metrics shift, 40% content change). When nothing is changing anymore, the system has settled — that's convergence. You set ε and max_iter; the engine stops itself.

**Propagation cost:** signals travel one hop per iteration. A four-node chain `A → B → C → D` needs at least 3 iterations for A's output to reach D. Design circuits knowing this.

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

## Signal

The unit of data flowing between nodes. Frozen struct — nodes read it, cannot mutate it.

| Field | Type | Meaning |
|---|---|---|
| `content` | str | The payload |
| `confidence` | float [0,1] | How sure the node is this answer is ready |
| `contradiction` | float [0,1] | How rejected/contradicted this signal is |
| `urgency` | float [0,1] | Time-sensitivity |
| `relevance` | float [0,1] | How on-task this signal is |
| `flags` | dict | Engine control (`consensus_locked`, `needs_synthesis`) — excluded from equality/hash |

`Signal.ZERO` is "nothing yet." Every node handles it gracefully as a no-op.

---

## Wire roles

Every wire tells the receiving node **why** it's getting that signal. Motor assembles a separate prompt section per role — the LLM literally sees different headers:

| Role | What it means | Motor sees |
|---|---|---|
| `context` | Normal upstream input (default) | `[CONTEXT]` |
| `peer` | Sibling at same stage, sharing results | `[PEER OUTPUTS]` |
| `feedback` | Downstream result looping back upstream | `[FEEDBACK FROM PREVIOUS ITERATION]` |

**When to use which:**
- `context` — one node informs another. `battery → motor`, `motor → gate`. Default, use most of the time.
- `peer` — two nodes at the same stage that should be aware of each other. Two reviewers both reading each other's drafts. Wire A→B peer AND B→A peer.
- `feedback` — you want downstream output to influence an upstream node in the next iteration. Creates an intentional cycle. The graph validator skips feedback wires when checking for illegal cycles — this is the only legal way to loop.

**Feedback pitfall:** if the feedback source is a blocked AND-gate, it sends `[BLOCKED: insufficient confidence]` as content. The upstream node then receives that as "feedback" and may not improve. Only use feedback when the signal flowing back is meaningful content.

---

## Engine loop

```
1. Initialize all outputs to Signal.ZERO
2. Inject user_prompt into Battery nodes
3. Run input-less nodes once (Bootstrap — Battery seeds before iteration 0)
4. For each iteration:
   a. Snapshot all current outputs
   b. Each node reads snapshot, computes new output
   c. aggregate_delta = mean(0.6 * metric_dist + 0.4 * content_change) across all nodes
   d. delta < epsilon → converged, stop
   e. consensus_locked flag set AND Sink has content → early exit
5. Return Sink's last received signal
```

**Why synchronous (Jacobi) update:** every node reads the *previous* iteration's outputs, not live updates. This means cycles are safe — a feedback edge brings last iteration's downstream output into this iteration's upstream input, exactly the discrete-time behavior wanted.

---

## Node types

### Battery
Static source. Emits `config.content + user_prompt` at confidence=1.0 every iteration.

```json
{ "id": "ctx", "type": "battery", "config": { "content": "Do the task.", "accumulate": false } }
```

`accumulate: true` — appends incoming `feedback` signals across iterations. Use this when the battery should grow its context from what reviewers say.

---

### Motor
LLM node. Calls `claude -p` via subprocess. The system prompt is your instructions; the engine prepends fixed confidence semantics (so you don't have to explain them yourself).

```json
{ "id": "agent", "type": "motor", "config": { "system": "You are a code reviewer." } }
```

Motor's final line **must** be `{"confidence": 0.X}` — this is how it reports confidence back to the engine.

**Cache:** same inputs → same output, no LLM call, delta=0. This is why circuits converge: once inputs stabilize, Motor returns the cached answer every iteration.

**Cache bypass:** if any input has `contradiction >= 0.8`, cache is skipped and a fresh LLM call is made. High contradiction means a reviewer rejected the answer — returning the cached rejected answer would be wrong.

**On error:** returns `Signal.ZERO`, logs to stderr. Never crashes the engine.

---

### Resistor
Single-input threshold filter. Pass or block, no attenuation.

```json
{ "id": "filter", "type": "resistor", "config": { "threshold": 0.55 } }
```

`confidence >= threshold` → pass through. Below → `Signal.ZERO`.

Use this before an AND-gate to drop low-quality signals before they can block consensus.

---

### AND Gate
Multi-input consensus gate. ALL inputs must exceed threshold — any failure blocks all.

```json
{
  "id": "gate",
  "type": "and_gate",
  "config": { "threshold": 0.55, "early_exit_threshold": 0.9, "merge_mode": "concat" }
}
```

**If all pass:** merges inputs by `merge_mode`:

| Mode | LLM? | Use when |
|---|---|---|
| `concat` (default) | No | Complementary specialists. Joins with `\n---\n`. |
| `dedupe` | No | Parallel samples of the same job. Line-level dedup. |
| `synthesize` | Yes (sets flag) | Disagreeing inputs. Wire output to a synthesizer Motor. |

**If any fail:** emits `Signal(confidence=0.0, contradiction=1.0)` — NOT `Signal.ZERO`. The `contradiction=1.0` triggers Motor cache bypass upstream, forcing a fresh LLM call. This is the retry mechanism — no explicit retry code needed.

**Early exit:** if passing and `min_confidence >= early_exit_threshold`, sets `consensus_locked=True`. Engine exits early without waiting for max_iter.

**Design note:** AND-gate threshold should reflect how strict your quality bar is. Too high (0.6+) and critics will block the gate every iteration, producing `[BLOCKED]` as feedback content, which causes oscillation without improvement.

---

### Sink
Terminal node. Records the highest-confidence signal it receives. Always returns `Signal.ZERO` (no out-edges).

```json
{ "id": "out", "type": "sink", "config": {} }
```

Engine reads `state["last_input"]` after the loop ends.

---

### Router
Branches on one input into N named outputs. Useful for routing easy prompts through a cheap path and hard prompts through a full pipeline.

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

Rules: `by_confidence`, `by_content_length`, `by_flag`. First match wins; one branch must be `"default": true`.

Router wires use `branch` instead of `role`:
```json
{ "from": "router", "to": "fast_motor", "branch": "fast" }
```

---

## Circuit design patterns

### Pattern 1: Linear pipeline (generation tasks)
Use when one stage refines the previous. No iteration needed — converges in 1–2 iterations.

```
battery → drafter → formatter → sink
```

Example: `examples/resume_html.json` — drafter organizes content, formatter writes HTML.

```powershell
python -m cirkit run examples\resume_html.json "Name: Jane Doe. Job: ..."
```

### Pattern 2: Parallel reviewers + consensus (critique tasks)
Use when multiple independent perspectives must agree before output advances.

```
battery ──► reviewer_A ──peer──► AND-gate ──► sink
        └──► reviewer_B ──peer──►
                 ▲                   │
                 └─────── feedback ──┘
```

Feedback wire: if AND-gate blocks, `contradiction=1.0` bypasses Motor cache → both reviewers revise → retry automatically.

**Key:** gate threshold should be 0.45–0.55. Too strict and `[BLOCKED]` flows as feedback content with no useful information.

Example: `examples/pr_review.json` — writer + security reviewer must agree.

### Pattern 3: Triage (cheap classifier + adaptive routing)
Use when some inputs are trivial and don't need a full pipeline.

```
battery → classifier → router → [fast: 2-node path]
                               → [slow: full 8-node path]
```

Trivial prompts skip the expensive path entirely.

---

## JSON schema

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

Validation on load: epsilon ∈ (0, 1.0], max_iter ≥ 1, all wire endpoints exist, no duplicate node IDs, sink has no out-edges, roles ∈ `{context, feedback, peer}`.

---

## Adding a node type

```python
# cirkit/nodes/mynode.py
from cirkit.nodes.base import Node
from cirkit.signal import Signal

class MyNode(Node):
    def __init__(self, config: dict):
        self.config = config

    def step(self, inputs: dict[str, list[Signal]], state: dict) -> Signal:
        # inputs keys are role strings: "context", "feedback", "peer"
        # state persists across iterations (use it for accumulation)
        # always return Signal, never None or raise
        ...
```

Register in `cirkit/nodes/__init__.py`:
```python
from cirkit.nodes.mynode import MyNode
NODE_REGISTRY["my_node"] = MyNode
```

`_maybe_cached_step` in `base.py` handles caching automatically. Override only if you need contradiction-bypass logic (like Motor does).

---

## Testing

```powershell
python -m pytest tests/ -v                        # 92 tests, <1s, no LLM calls
python -m pytest tests/test_engine_no_motor.py -v # core thesis: engine works without Motor
```

---

## File structure

```
cirkit/
├── __init__.py       # Public API: Circuit, Signal, run, load_circuit
├── __main__.py       # CLI entry point
├── signal.py         # Signal dataclass + ZERO sentinel
├── convergence.py    # delta() + aggregate_delta()
├── graph.py          # Circuit, Wire, load_circuit() with full JSON validation
├── engine.py         # Synchronous Jacobi update loop
├── state.py          # RunState, RunResult
├── llm.py            # call_claude() subprocess wrapper
├── confidence.py     # Trailing-JSON parser + heuristic fallback + hedge cap
└── nodes/
    ├── __init__.py   # NODE_REGISTRY (type string → class)
    ├── base.py       # Node ABC + _maybe_cached_step (lazy cache)
    ├── battery.py
    ├── sink.py
    ├── resistor.py
    ├── and_gate.py
    ├── router.py
    └── motor.py      # LLM node; overrides _maybe_cached_step with contradiction bypass

tests/                # 92 unit tests — see test_engine_no_motor.py for core thesis proof
examples/
├── pr_review.json    # Parallel reviewers + consensus + synthesizer
└── resume_html.json  # Linear pipeline: drafter → HTML formatter
```

---

## Output

```
[converged after N iter, final delta=0.XXXX]
<sink content>
```

Non-convergent (hit max_iter):
```
[MAX_ITER (non-convergent) after N iter, final delta=0.XXXX]
<last signal that reached Sink>
```

Non-convergence is reported, never raised. The output is still whatever reached the Sink.
