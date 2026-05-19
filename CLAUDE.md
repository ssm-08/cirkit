# CirKit

Signal circuit reasoning engine. Graph of stateful nodes propagate typed Signals until Δ < ε convergence. LLM (Motor) is one node type, not the orchestrator.

## Stack
- Python 3.11+ (machine runs 3.14 — compatible)
- LLM via `claude -p` subprocess (stdin, not argv — Windows quoting safety)
- Circuit defined in JSON; no API keys needed

## Project layout
- `cirkit/` — core engine (signal, convergence, graph, engine, llm, confidence)
- `cirkit/nodes/` — Battery, Sink, Resistor, AndGate, Router, Motor
- `tests/` — 135 unit tests, all no-LLM except mock motor tests
- `examples/pr_review.json` — canonical demo circuit (writer+security→gate→synthesizer; feedback from synthesizer back to motors)
- `examples/resume_html.json` — linear pipeline demo (drafter → HTML coder, no feedback loop)
- `ui/index.html` — standalone circuit builder UI (single file, no build step)
- `ui/server.py` — stdlib dev server (no Django); run: `python ui/server.py [port]` default 8080
- `ui/views.py` + `ui/urls.py` — Django integration (StreamingHttpResponse, SSE-style ndjson)
- `ui/circuit_utils.py` — shared parse/validate logic imported by both server.py and views.py

## Setup
- `pip install -e ".[test]"` — installs cirkit + pytest (required for tests); use this form for CI
- `pip install -e ".[docs]"` — installs cirkit + mkdocs-material for local docsite work
- `pip install -e .` — bare install, no test/docs extras; sufficient for running circuits

## Commands
- `python -m pytest tests/ -v` — run all 135 tests (fast, <1s, no LLM calls)
- `python -m pytest tests/test_engine_no_motor.py -v` — core thesis proof
- `python -m cirkit run examples\pr_review.json "<prompt>"` — end-to-end (needs claude CLI)
- `python ui/server.py` — dev UI at http://localhost:8080/ (no Django needed)

## JSON circuit schema (quick ref)
`config`: `{epsilon, max_iter}` | `sink`: node id | `nodes`: `[{id, type, config}]` | `wires`: `[{from, to, role}]`
Valid roles: `context` (default) | `feedback` | `peer`. Router wires use `branch` instead of `role` — Router wires must NOT have both `branch` and `role`.

## Adding a node type
1. Create `cirkit/nodes/<name>.py`, subclass `Node`, implement `step(inputs, state) -> Signal`
2. Register: `NODE_REGISTRY["<name>"] = MyNode` (in module or `nodes/__init__.py`)
3. `_maybe_cached_step` in base handles R12 lazy cache; override only if node needs R2 contradiction bypass (like Motor)

## Key invariants
- `Signal` is frozen; `flags` stored as `MappingProxyType` (truly immutable — `frozen=True` alone doesn't prevent in-place dict mutation); excluded from equality/hash (`compare=False, hash=False`)
- `_maybe_cached_step` in base Node filters `Signal.ZERO` from cache key (C1) — consistent with Motor. Prevents spurious cache misses when zero-padded inputs arrive.
- **Cache-miss convergence**: `aggregate_delta` in engine is computed over cache-miss nodes only (`new_outputs[n] is not prev_outputs[n]`). Cache hit = same object = provable delta=0 = excluded from mean. Battery (stable after iter 1) and Sink (always ZERO) self-exclude automatically. No epsilon dilution tuning needed.
- **1-iter lag**: ALL wires carry prev-iter output. Peer/feedback wires deliver `Signal.ZERO` on iter 1 (sibling/downstream had no output yet). Peer content arrives iter 2+. This is fundamental to the Jacobi model — not a bug.
- `Battery` requires `"content"` in config — raises `ValueError` at `__init__` time if missing (not deferred to `step()`)
- Blocked AND-Gate emits `contradiction=1.0` — NOT `Signal.ZERO` (triggers R2 cache bypass upstream)
- Engine R9 bootstrap: inject `user_prompt` into Battery state BEFORE running input-less nodes
- Router wires must have `branch` field and must NOT also have `role` field — having both bypasses cycle detection
- NODE_REGISTRY: populated in `nodes/__init__.py` (all node types including Motor registered there)

## Circuit design lessons
- **Linear generation tasks** (resume, report, transform): use simple `battery → motor(s) → sink`. No feedback loop, no gate. Converges in 1–2 iter.
- **Critic+gate feedback pitfall**: if critic system prompt says "output LOW confidence if issues found", gate blocks every iteration, sends `[BLOCKED: insufficient confidence]` as feedback content, upstream Motor gets useless signal and oscillates until MAX_ITER. Fix: lower gate threshold (0.45–0.55) OR remove critic+gate entirely for generation tasks.
- **Confidence = completeness, not outcome**: Motor system prompts must rate confidence on how thorough the analysis is — NOT on whether issues were found. "HIGH confidence if no vulnerabilities" breaks the gate.
- **Feedback source matters**: wire feedback from `synthesizer` (or any node with real output content), never from `gate` when gate may block. Blocked gate sends `[BLOCKED]` which is useless. Synthesizer sends actual fused content motors can refine against.
- **Resistor before gate is redundant**: if resistor threshold == gate threshold, the resistor adds no value — gate already rejects low-confidence peers. Only use resistor if you want to raise the bar for one peer above the gate's general threshold.
- **AND-gate threshold sweet spot**: 0.45–0.55 for most cases. Above 0.6 risks blocking oscillation on iterative refinement circuits.
- **Convergence epsilon**: `aggregate_delta` scoped to cache-miss nodes only — Battery/Sink self-exclude. Start at `epsilon: 0.05`; lower to 0.01–0.03 for dense feedback loops with many active motors. No manual dilution correction needed.
- **`accumulate: false` is redundant**: Battery's `accumulate` defaults to `False` — no need to set it explicitly in JSON.
- **Feedback wire only useful when**: the signal flowing back is meaningful content (synthesizer output, critique text). Never useful when source is a blocked gate.
- **Wire role semantics**: `context` = default for all upstream/sequential wires (battery→motor, motor→gate, gate→sink). `peer` = Motor-to-Motor sibling awareness only (reviewer reading writer's draft; bidirectional = two separate wires). `feedback` = back-edge structural requirement (downstream→upstream); also frames signal as "refine against this" in motor prompt. Only Motor uses role framing — AND-gate, Resistor, Sink ignore role entirely.
- **motor→gate wires use `context` not `peer`**: AND-gate ignores role, but `context` is semantically correct (gate is downstream of motors, not a sibling).
- **Reviewer needs peer wire from writer**: In writer+reviewer circuits, battery→reviewer gives task context but reviewer CANNOT see the written content without a `writer→reviewer (peer)` wire. Always add this wire or reviewer has nothing to review.
- **Parallel independent reviewers need no peer wires between them**: If two motors both analyze the same input (e.g., code-review + security-review of the same PR), only `battery → each motor` wires are needed. Do NOT add `motor_A → motor_B (peer)` unless you explicitly want one to see the other's draft.
- **merge_mode: synthesize does NOT call the LLM**: AND-Gate `synthesize` mode only concatenates inputs and sets `flags["needs_synthesis"] = True`. A downstream synthesizer Motor reads that flag and does the actual LLM call. Without the Motor, the flag does nothing. `concat` mode suffices if you don't need LLM-quality fusion — wire gate directly to Sink.
- **Gate-block + synthesizer feedback**: when AND-Gate blocks, it emits `Signal(contradiction=1.0, content="[BLOCKED]")` — NOT ZERO. Synthesizer still runs (R2 bypass), but its input is "[BLOCKED]" → produces low-quality output → poor feedback to motors. Retries still happen (changing synthesizer output = cache miss for motors) but feedback content is useless. Design circuits so gate nearly always passes (threshold 0.45–0.55); gate blocking is an edge case, not the normal operating mode.

## Workflow
When user says "clear", "ready to clear", or similar — before clearing:
1. Update CLAUDE.md, README.md, and any relevant `docs/` pages with learnings from the session (new patterns, gotchas, schema changes, node behavior, anything that helps future sessions).
2. Commit and push so the live docsite reflects the changes: `git add docs/ mkdocs.yml CLAUDE.md README.md && git commit && git push`.

## UI architecture
- Single-file app (`ui/index.html`) — all CSS/JS inline, no build step, no dependencies except Google Fonts
- Design tokens: JetBrains Mono (dominant), IBM Plex Sans (prose), Outfit 700 (wordmark)
- Implemented node types in UI: battery, motor, resistor, and_gate, router, sink
- NOT implemented (greyed out, `.off` class): or_gate, xor_gate
- Wire roles: context (gray solid) | peer (teal solid) | feedback (amber dashed)
- Canvas zoom: mouse wheel or +/−/⌂ overlay (bottom-left); range 25%–250%; `transform: scale(zoom)` on `#canvas`
- All canvas coordinate math divides by `zoom` — drop, drag, portCenter, wire drawing
- Resizable panels: drag 4px `.rhandle` (sides) or `.hhandle` (bottom bar); palette/inspector 120–400px, output 60–500px
- Backend wiring: `POST /cirkit/validate/` → validates JSON; `POST /cirkit/run/` → streams ndjson events
- Event types from server: `{type:"iter"}`, `{type:"node"}`, `{type:"output"}`, `{type:"done"}`, `{type:"error"}`
- `node` event: `{type:"node", id, conf, contra, cached}` — emitted per-node per-iter; drives live card updates
- Demo mode fallback: if `/cirkit/validate/` unreachable, runs 4-iter simulation (no backend needed)
- `server.py` sets PYTHONPATH to project root so `cirkit` package is importable without install
- Output drawer: three persistent sub-divs `#ob-log / #ob-out / #ob-json` — `outTab()` shows/hides, never clears
- Signal pulses: `<animateMotion>` SVG circles per wire while running; colored by role (context=steel-blue, peer=teal, feedback=amber)
- Node fire flash: `color-mix(in srgb, var(--nc) 14%, ...)` background + 'FIRE' label for 220ms when `k=0` (step() called, not cached)
- Runtime ticker: `setInterval` 100ms updates elapsed time in statebar independently of event arrival
- `circuit_utils.py` shared by server.py and views.py — `validate_circuit()` + `parse_cirkit_line()` (handles iter/node/done/converged lines); validates node config fields (battery requires `content`, and_gate/resistor require `threshold`)
- `views.py` `run_circuit` validates circuit via `validate_circuit()` BEFORE spawning subprocess — returns 400 JSON on errors

## UI state variables (key)
- `sel` — selected node id (string or null)
- `selWire` — selected wire index into `wires[]` (int or null); cleared in selectNode, deselect, delNode, setBranches, clearCanvas
- `going` — true while circuit is running
- `abortCtrl` — AbortController instance during run (nulled on done/stop/error)
- `demoTimer` — setTimeout ID for demo mode steps (enables cancellation)
- `ticker` — setInterval ID for elapsed-time counter

## UI wire selection system
- `drawWires()` appends transparent 12px hit paths (`pointer-events:all`) LAST — overrides `#wsvg { pointer-events:none }` per-element; collects in `hits[]` array then appends after all visual paths
- Selected wire renders halo (6px semi-transparent role-colored path) + thicker stroke (2.5px)
- `selectWire(i)` — sets selWire, clears node selection, redraws, calls showWireInsp(i)
- `showWireInsp(i)` — inspector shows From/To (readonly), role `<select>` (non-branch) or branch (readonly), Delete button
- `setWireRole(i, role)` — mutates wires[i].role, redraws
- `delWire(i)` — splice + null selWire + redraw + reset inspector
- `inspTab()` restores wire inspector on tab round-trip: `selWire !== null ? showWireInsp(selWire) : showNodeInsp(sel)`

## UI run lifecycle
- Validation happens BEFORE setting RUNNING state — if invalid, button re-enabled, status stays unchanged
- `runCircuit()`: disable button → create AbortController → validate → (on pass) set going=true + RUNNING UI + setRunBtn(true) + lockCanvas() → run
- `done()`: guarded with `if (!going) return` to prevent double-invocation when stopCircuit() fires before runReal()/runDemo() exit
- `stopCircuit()`: abort + clear demoTimer + going=false + clear ticker + resetRS() + setRunBtn(false) + unlockCanvas()
- `setRunBtn(running)`: swaps button label/onclick between RUN and STOP
- `lockCanvas()` / `unlockCanvas()`: toggle `.locked` class on `#cwrap` and `#palette` (CSS: pointer-events:none + opacity:0.65)

## Windows gotchas
- **Unicode in print()**: Windows PowerShell defaults to CP1252 — avoid non-ASCII chars in server startup prints. Use `->` not `→`. If needed, set `PYTHONIOENCODING=utf-8`.
- **server.py background job**: `serve_forever()` blocks the terminal — that's normal, not a hang.

## Docsite & CI infrastructure
- `mkdocs.yml` + `docs/` — MkDocs Material docsite; 17 pages (index + 5 concepts + 5 guides + 6 reference incl. architecture + roadmap)
- Mermaid diagrams enabled via `pymdownx.superfences` custom_fences in mkdocs.yml — use ` ```mermaid ` blocks
- Install docs deps: `pip install -e ".[docs]"` → then `mkdocs serve` or `mkdocs build --strict`
- `.github/workflows/ci.yml` — Python 3.11/3.12/3.13 matrix; installs `pip install -e ".[test]"` (includes pytest); no coverage gating, no lint
- `.github/workflows/docs.yml` — triggers on push to master when `docs/**` or `mkdocs.yml` changes + `workflow_dispatch` for manual trigger; deploys via `actions/deploy-pages` (requires Pages source = "GitHub Actions" in repo settings, NOT "Deploy from branch")
- Python 3.14 has no GitHub Actions runner — CI matrix stops at 3.13
- **CI pyproject.toml invariants**: build-backend must be `setuptools.build_meta` (not `setuptools.backends.legacy` — fails on Python 3.11 CI); `[tool.setuptools.packages.find] include = ["cirkit*"]` required to exclude `ui/` from package discovery; pytest lives in `[project.optional-dependencies] test`

## Motor efficiency (Phase 1 — sessions + delta)
- **`llm.call_claude` returns `LLMResult` dataclass** (not `str`): `content`, `tokens_in`, `tokens_out`, `cost_usd`. Any test mock patching `cirkit.llm.call_claude` must return `LLMResult`, not a plain string.
- **`fake_llm` signature in tests**: `def fake_llm(prompt, *, session_id=None, model=None, timeout=60)` — Motor passes all three kwargs; old-style `fake_llm(prompt, timeout=60)` raises `TypeError`.
- **Session-based delta prompting**: each Motor gets a unique UUID `session_id` per `circuit.run()` call (injected by engine bootstrap). On iter 1, Motor sends full prompt. On iter 2+, if `session_id` is set and sections changed, sends delta prompt (only changed `[CONTEXT]`/`[PEER OUTPUTS]`/`[FEEDBACK]` sections) to the same session. Fail-soft: on delta send failure, retries with full prompt.
- **Empty-input guard**: Motor skips LLM call and returns `Signal.ZERO` if all input roles have no non-zero content. Prevents wasted calls when a Motor wakes before upstream nodes have fired.
- **Per-motor model selection**: add optional `"model"` field to Motor JSON config. Maps to `claude --model <name>`. Unset = CLI default. Use `"haiku"` for low-stakes nodes (~10x cheaper). Security/synthesis nodes should stay on default (Sonnet/Opus).
- **Token tracking**: `RunResult` now has `total_tokens_in`, `total_tokens_out`, `total_cost_usd`, `per_motor_usage` (dict of node_id → list of per-call entries). CLI emits `[cost tokens_in=N tokens_out=M cost_usd=$X.XX]` after convergence line. `parse_cirkit_line` handles `[cost ...]` → `{type:"cost", ...}`.
- **MOTOR_PREFIX trimmed**: ~250 tokens → ~120 tokens. Same rules, more compact. Risk: subtle behavior shifts. If motor quality degrades, compare against git history.
- **Phase 2 (deferred)**: drop CLI subprocess, switch to `anthropic.Anthropic().messages.create()` with `cache_control: {type: "ephemeral"}` on prefix + system. Targets 70-80% savings via server-side prompt cache. Requires API key, async, separate plan.

## Read tool quirk
After writing files, use `Bash cat` to read externally-modified versions — `Read` tool returns stale content after a `Write`.

## Branch
Default branch is `master` (not `main`).
