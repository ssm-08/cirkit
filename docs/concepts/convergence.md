# Convergence

CirKit terminates when the circuit's aggregate delta falls below `epsilon` or when `max_iter` is reached.

## Per-node delta

For each node, the delta between iteration N−1 and N is:

```
delta(prev, curr) = 0.9 × metric_distance + 0.1 × content_change
```

- `metric_distance` = Euclidean norm of `(Δconf, Δcontra, Δurgency, Δrelevance)` / 2, clamped to `[0, 1]`
- `content_change` = 1 if `SHA1(content)` changed, 0 if identical

The 0.9/0.1 weighting reflects a key empirical finding: LLMs produce slightly different text on every call even with identical prompts. A 0.4 content weight made feedback-loop circuits unconvergeable — delta was permanently ≥ 0.4 regardless of metric stability. Metric convergence is the real signal; content drift is noise. The 0.1 weight catches dramatic answer flips (complete content change with stable metrics) without blocking convergence from minor wording variation.

## Aggregate delta

The engine computes delta only over **cache-miss nodes** — nodes whose output changed from the previous iteration. Nodes with a cache hit (identical inputs → identical output object) contribute a provable delta of zero and are excluded from the mean.

```
active_nodes = {n for n in all_nodes if output_changed(n)}
aggregate_delta = mean(delta(n) for n in active_nodes)
```

If no nodes changed (everything cached), `aggregate_delta = 0.0` and the circuit converges immediately — nothing is still moving.

This means Battery (stable after iteration 1) and Sink (always outputs `Signal.ZERO`) are automatically excluded from the convergence calculation. Only nodes that are actually changing drive the delta.

## Epsilon tuning

`epsilon` is the convergence threshold. The circuit stops when `aggregate_delta < epsilon`.

Since only active nodes contribute to the mean, epsilon directly reflects what the changing nodes are doing — no dilution from stable nodes. Start at `epsilon: 0.05` and adjust based on observed behavior:

| Situation | Recommended epsilon |
|-----------|---------------------|
| Linear pipeline (no feedback) | 0.05–0.1 |
| Parallel motors + gate, no feedback | 0.05 |
| Feedback loop between motors | 0.15 |
| Feedback loop + gate→motor feedback | 0.15 |

If the circuit exits too early (output quality low): lower epsilon.  
If the circuit runs too many iterations unnecessarily: raise epsilon.

## max_iter as a safety net

`max_iter` prevents infinite loops in circuits that oscillate — typically caused by:

- AND-Gate threshold too high (motors can't converge to passing confidence)
- Motor system prompt that rates confidence on outcome, not completeness
- Motor confidence that never reaches the gate threshold (tune threshold down or fix system prompt)

If the circuit hits `max_iter` regularly, fix the root cause rather than raising `max_iter`.

## Early exit

If an AND-Gate's `early_exit_threshold` is reached (all inputs meet this higher bar) AND the Sink has received a positive-confidence signal, the engine exits immediately via the `consensus_locked` flag — even if `aggregate_delta` hasn't crossed `epsilon` yet. This is the R4/G14 optimization for circuits that reach strong consensus before geometric convergence.
