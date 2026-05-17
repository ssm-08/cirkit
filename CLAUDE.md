# CirKit

Signal circuit reasoning engine. Graph of stateful nodes propagate typed Signals until Δ < ε convergence. LLM (Motor) is one node type, not the orchestrator.

## Stack
- Python 3.11+ (machine runs 3.14 — compatible)
- LLM via `claude -p` subprocess (stdin, not argv — Windows quoting safety)
- Circuit defined in JSON; no API keys needed

## Project layout
- `cirkit/` — core engine (signal, convergence, graph, engine, llm, confidence)
- `cirkit/nodes/` — Battery, Sink, Resistor, AndGate, Router, Motor
- `tests/` — 92 unit tests, all no-LLM except mock motor tests
- `examples/pr_review.json` — canonical demo circuit (writer+security+synthesizer)
- `examples/resume_html.json` — linear pipeline demo (drafter → HTML coder, no feedback loop)

## Setup
- `pip install -e .` — installs `cirkit` CLI entry point; not required for `python -m cirkit`

## Commands
- `python -m pytest tests/ -v` — run all 92 tests (fast, <1s, no LLM calls)
- `python -m pytest tests/test_engine_no_motor.py -v` — core thesis proof
- `python -m cirkit run examples\pr_review.json "<prompt>"` — end-to-end (needs claude CLI)

## JSON circuit schema (quick ref)
`config`: `{epsilon, max_iter}` | `sink`: node id | `nodes`: `[{id, type, config}]` | `wires`: `[{from, to, role}]`
Valid roles: `context` (default) | `feedback` | `peer`. Router wires use `branch` instead of `role`.

## Adding a node type
1. Create `cirkit/nodes/<name>.py`, subclass `Node`, implement `step(inputs, state) -> Signal`
2. Register: `NODE_REGISTRY["<name>"] = MyNode` (in module or `nodes/__init__.py`)
3. `_maybe_cached_step` in base handles R12 lazy cache; override only if node needs R2 contradiction bypass (like Motor)

## Key invariants
- `Signal` is frozen; `flags` dict excluded from equality/hash (`compare=False, hash=False`)
- Blocked AND-Gate emits `contradiction=1.0` — NOT `Signal.ZERO` (triggers R2 cache bypass upstream)
- Engine R9 bootstrap: inject `user_prompt` into Battery state BEFORE running input-less nodes
- NODE_REGISTRY: populated in `nodes/__init__.py`; Motor added via `cirkit/__init__.py → import cirkit.nodes.motor`

## Circuit design lessons
- **Linear generation tasks** (resume, report, transform): use simple `battery → motor(s) → sink`. No feedback loop, no gate. Converges in 1–2 iter.
- **Critic+gate feedback pitfall**: if critic system prompt says "output LOW confidence if issues found", gate blocks every iteration, sends `[BLOCKED: insufficient confidence]` as feedback content, upstream Motor gets useless signal and oscillates until MAX_ITER. Fix: lower gate threshold (0.45–0.55) OR remove critic+gate entirely for generation tasks.
- **AND-gate threshold sweet spot**: 0.45–0.55 for most cases. Above 0.6 risks blocking oscillation on iterative refinement circuits.
- **Feedback wire only useful when**: the signal flowing back is meaningful content (synthesizer output, critique text). Never useful when source is a blocked gate.

## Workflow
When user says "clear", "ready to clear", or similar — before clearing, update CLAUDE.md, README.md, and any other context/doc files with learnings from the session (new patterns, gotchas, schema changes, node behavior, anything that helps future sessions).

## Read tool quirk
After writing files, use `Bash cat` to read externally-modified versions — `Read` tool returns stale content after a `Write`.

## Branch
Default branch is `master` (not `main`).
