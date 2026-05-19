# Signals

A `Signal` is the unit of information that flows between nodes. It is immutable — once created, it cannot be changed.

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `content` | `str` | The text payload — what the node produced |
| `confidence` | `float` | 0.0–1.0. How complete or ready this output is |
| `contradiction` | `float` | 0.0–1.0. Tension with other signals; ≥ 0.8 triggers upstream cache bypass |
| `urgency` | `float` | 0.0–1.0. Priority weight (factored into convergence delta) |
| `relevance` | `float` | 0.0–1.0. Tie-break for Sink selection |
| `flags` | `Mapping[str, Any]` | Immutable metadata (e.g. `consensus_locked`) |

`flags` are excluded from equality and hashing — two signals with identical metrics and content are considered equal regardless of their flags.

## Signal.ZERO

`Signal.ZERO` is the sentinel value: empty content, all metrics 0.0, no flags.

It means "no output yet" or "this node was not activated." Key behaviors:

- **Sink ignores ZERO inputs** — won't overwrite a real previous output with an empty signal.
- **Cache filters ZERO** — ZERO inputs are excluded from cache keys (C1 rule) to prevent spurious cache misses when zero-padded inputs arrive in different orders.
- **AND-Gate treats ZERO as "no vote"** — a ZERO input doesn't count as a failing peer.

## Immutability

`Signal` is a `dataclass(frozen=True)`. The `flags` field is additionally wrapped in `MappingProxyType` — `frozen=True` prevents attribute reassignment but doesn't stop in-place dict mutation. The proxy makes mutation impossible at the data structure level.

## Confidence semantics

Confidence means **"how complete is this output"**, not "how favorable is the result."

- A security reviewer who finds no vulnerabilities should output **high** confidence — the analysis is thorough.
- A reviewer who only skimmed the first file should output **low** confidence — the analysis is incomplete.

This distinction matters for AND-Gate: if motors rate confidence on outcome ("no bugs found → high confidence"), the gate passes trivially on incomplete work. See [Circuit Design Patterns](../guides/circuit-design.md) for the full pitfall.

## The convergence delta

Each iteration, the engine computes a delta between the previous and current output for every node:

```
delta = 0.9 × metric_distance + 0.1 × content_change
```

`metric_distance` = Euclidean norm of `(confidence, contradiction, urgency, relevance)` / 2, clamped to `[0, 1]`.
`content_change` = 1 if SHA1(content) changed, 0 otherwise.

The 0.9/0.1 weighting is intentional — LLMs produce slightly different text on every call even with identical prompts, so content drift is noise. Metric stability is the real convergence signal.

The circuit converges when `mean(delta across all nodes) < epsilon`. See [Convergence](convergence.md) for tuning guidance.
