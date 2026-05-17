# Convergence

CirKit terminates when the circuit's aggregate delta falls below `epsilon` or when `max_iter` is reached.

## Per-node delta

For each node, the delta between iteration N−1 and N is:

```
delta(prev, curr) = 0.6 × metric_distance + 0.4 × content_change
```

- `metric_distance` = Euclidean norm of `(Δconf, Δcontra, Δurgency, Δrelevance)` / 2, clamped to `[0, 1]`
- `content_change` = 1 if `SHA1(content)` changed, 0 if identical

The 0.6/0.4 weighting treats content change as less decisive than metric drift — a node that produces the same text but with higher confidence should still count as progressing.

## Aggregate delta

```
aggregate_delta = mean(delta(node) for all nodes)
```

The circuit converges when `aggregate_delta < epsilon`.

## Epsilon dilution — the critical tuning issue

`aggregate_delta` is a mean across **all** nodes, including constant-output nodes. A Sink always emits `Signal.ZERO`, so its delta is always 0. In a 5-node circuit with 1 actively-changing Motor, the Motor's real delta is diluted by a factor of 5 in the aggregate.

**Rule**: in a circuit with N total nodes and M actively-changing nodes, effective epsilon sensitivity is approximately `epsilon × (N / M)`.

For a typical 5-node PR-review circuit (Battery + 2 Motors + AndGate + Sink), only the Motors and gate change between iterations. Use `epsilon` around 0.05; for circuits where only 1 of 8 nodes is active, consider 0.01.

## Practical tuning guide

| Situation | Recommended epsilon |
|-----------|---------------------|
| Linear pipeline (1–2 active nodes) | 0.05–0.1 |
| Parallel review + gate (3–4 active) | 0.03–0.05 |
| Dense feedback loop (5+ active) | 0.01–0.03 |

Start at `epsilon: 0.05` and lower if the circuit exits too early before quality stabilizes.

## max_iter as a safety net

`max_iter` prevents infinite loops in circuits that oscillate — typically caused by:

- AND-Gate threshold too high (motors can't converge to passing confidence)
- Motor system prompt that rates confidence on outcome, not completeness
- Feedback wire from a blocked gate (sends `[BLOCKED]` which has zero useful content)

If the circuit hits `max_iter` regularly, fix the root cause rather than raising `max_iter`.

## Early exit

If an AND-Gate's `early_exit_threshold` is reached (all inputs meet this higher bar) AND the Sink has received a positive-confidence signal, the engine exits immediately via the `consensus_locked` flag — even if `aggregate_delta` hasn't crossed `epsilon` yet. This is the R4/G14 optimization for circuits that reach strong consensus before geometric convergence.
