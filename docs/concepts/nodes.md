# Nodes

Every node in a circuit is a subclass of `Node`. Each iteration, the engine calls `_maybe_cached_step(inputs, state) → Signal`. Nodes are stateless between calls except through the `state` dict the engine passes in and preserves across iterations.

See [Node Config reference](../reference/node-config.md) for all config fields.

## Battery

**Emits a fixed signal every iteration.** Use it to inject the user prompt and task description.

```json
{
  "id": "task",
  "type": "battery",
  "config": {
    "content": "You are a senior engineer. Review the following PR for correctness and security."
  }
}
```

- `content` is **required** — raises `ValueError` at load time if missing.
- Output confidence is always 1.0.
- `accumulate: true` (optional, default `false`): appends incoming feedback signals to the emitted content each iteration. Use when you want the battery to "remember" feedback from a synthesizer and pass it downstream in subsequent rounds.

## Motor

**Calls the LLM.** The system prompt is the `system` config field; the assembled user prompt comes from incoming wire signals grouped by role.

```json
{
  "id": "writer",
  "type": "motor",
  "config": {
    "system": "You are a technical writer. Draft clear documentation. Rate your confidence as JSON on the last line: {\"confidence\": 0.9}"
  }
}
```

Motor assembles the prompt in sections:

- Wires with `role: context` → `[CONTEXT]` section
- Wires with `role: peer` → `[PEER OUTPUTS]` section (multiple peers enumerated as `PEER 1:`, `PEER 2:`, etc.)
- Wires with `role: feedback` → `[FEEDBACK FROM PREVIOUS ITERATION]` section

The LLM output must end with `{"confidence": X}` on the last non-empty line. If absent, confidence is estimated from output length and hedge phrases.

**Cache**: 64-entry LRU, keyed by sorted input content hashes. If any input has `contradiction ≥ 0.8`, the cache is bypassed and the LLM is called fresh (R2 rule).

## Resistor

**Single-input threshold gate.** Passes the signal unchanged if `confidence ≥ threshold`; otherwise emits `Signal.ZERO`.

```json
{"id": "filter", "type": "resistor", "config": {"threshold": 0.7}}
```

Use a Resistor to raise the bar for one specific input above what the downstream AND-Gate requires. If the Resistor threshold equals the gate threshold, it is redundant — the gate already rejects low-confidence peers.

## AndGate

**Consensus gate.** Passes only when ALL non-ZERO inputs have `confidence ≥ threshold`.

```json
{
  "id": "gate",
  "type": "and_gate",
  "config": {
    "threshold": 0.5,
    "merge_mode": "synthesize",
    "early_exit_threshold": 0.9
  }
}
```

| Config | Default | Description |
|--------|---------|-------------|
| `threshold` | required | Minimum confidence all inputs must meet |
| `merge_mode` | `"concat"` | How to combine passing inputs: `concat`, `dedupe`, `synthesize` |
| `early_exit_threshold` | `1.0` | If min confidence ≥ this, sets `consensus_locked` flag for early circuit exit |

**Merge modes:**

- `concat` — join with `\n---\n`, no LLM. Wire gate directly to Sink when this is sufficient.
- `dedupe` — line-level case-insensitive deduplication, preserve first-occurrence order, no LLM
- `synthesize` — same as `concat`, plus sets `flags["needs_synthesis"] = True`. This flag does **not** call the LLM — it signals a downstream synthesizer Motor to do the actual LLM fusion. Without a Motor downstream, this flag goes nowhere.

When blocked, the gate emits `contradiction = 1.0` (not `Signal.ZERO`). This triggers the R2 cache bypass in upstream Motors, forcing them to re-run with the contradiction as implicit feedback.

**Threshold sweet spot**: 0.45–0.55 for most circuits. Above 0.6 risks blocking oscillation.

## Router

**Content-based dispatcher.** Routes one input signal to one of N named branches based on a configurable rule.

```json
{
  "id": "triage",
  "type": "router",
  "config": {
    "rule": "by_confidence",
    "branches": [
      {"branch": "high", "min_confidence": 0.8},
      {"branch": "low", "default": true}
    ]
  }
}
```

| Rule | Branch field | Description |
|------|-------------|-------------|
| `by_confidence` | `min_confidence` | First branch whose threshold the input meets |
| `by_content_length` | `max_length` | First branch whose length limit the input fits within |
| `by_flag` | `flag_name` | First branch whose flag is set on the signal |

Exactly one branch must declare `"default": true` as fallback.

Router out-edges use `branch` instead of `role` — and must NOT also include a `role` field.

## Sink

**Terminal collector.** Always the circuit's final node; its `id` is the top-level `sink` field.

The Sink selects the highest-confidence incoming signal (tie-break: `relevance`), stores it in state, and returns `Signal.ZERO`. After the loop, the engine reads `state["last_input"]` from the Sink as the circuit's final output. ZERO inputs are ignored — the Sink never overwrites real content with an empty signal.
