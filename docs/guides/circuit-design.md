# Circuit Design Patterns

## Pattern 1 — Linear pipeline

**When to use**: generation tasks (write a report, convert format, summarize). No iteration needed.

```
Battery ──context──► Motor ──► Motor ──► Sink
```

```json
{
  "config": {"epsilon": 0.05, "max_iter": 3},
  "sink": "out",
  "nodes": [
    {"id": "task", "type": "battery", "config": {"content": "Draft resume HTML for:"}},
    {"id": "drafter", "type": "motor", "config": {"system": "Draft prose resume. End with {\"confidence\": 0.9}."}},
    {"id": "coder", "type": "motor", "config": {"system": "Convert prose resume to HTML. End with {\"confidence\": 0.9}."}},
    {"id": "out", "type": "sink", "config": {}}
  ],
  "wires": [
    {"from": "task", "to": "drafter", "role": "context"},
    {"from": "drafter", "to": "coder", "role": "peer"},
    {"from": "coder", "to": "out", "role": "context"}
  ]
}
```

Converges in 1–2 iterations. Don't add a gate or feedback loop — there's no debate to resolve.

## Pattern 2 — Parallel review + consensus gate

**When to use**: tasks that benefit from multiple independent perspectives before a combined output.

```
Battery ──context──► Motor A ──peer──► AND-Gate ──► Synthesizer ──► Sink
                   ► Motor B ──peer──►
```

See `examples/pr_review.json` for a complete working example.

**Key wiring rules**:

- Battery → each Motor with `role: context` (task description)
- Each Motor → AND-Gate with `role: peer`
- AND-Gate threshold: 0.45–0.55
- Synthesizer → Sink with `role: context`

**Add a feedback loop** when you want motors to refine based on synthesis:

```
Synthesizer ──feedback──► Motor A
            ──feedback──► Motor B
```

Wire feedback **from the Synthesizer**, never from the gate. A blocked gate emits `[BLOCKED]`, which is useless as feedback content.

## Pattern 3 — Content routing

**When to use**: dispatch to different specialist motors based on the input signal's properties.

```
Battery ──context──► Router ──high──► Fast Motor ──► Sink
                          ──low───► Deep Motor ──►
```

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

---

## Pitfalls

### Critic gates every iteration (oscillation)

**Symptom**: circuit hits `max_iter` every run. Delta never converges. Gate always blocked.

**Cause**: Motor system prompt says "output LOW confidence if issues found." Gate blocks. Gate sends `[BLOCKED: insufficient confidence]` as feedback. Motors re-run with useless feedback. Repeat.

**Fix**: Motor confidence must reflect *completeness of analysis*, not *absence of issues*. A reviewer who finds 5 bugs but analyzed all 10 files thoroughly should output high confidence.

```
WRONG: "Output confidence: 0.9 if no vulnerabilities found."
RIGHT: "Output confidence: 0.9 if you reviewed all aspects of the change thoroughly."
```

### Reviewer can't see the written content

**Symptom**: reviewer output is generic; ignores the specific content it should critique.

**Cause**: only `battery → reviewer` wire was added. Reviewer sees the task but not the writer's output.

**Fix**: add `writer → reviewer` with `role: peer`.

### Feedback from a blocked gate

**Symptom**: motors oscillate; feedback content is `[BLOCKED: insufficient confidence]`.

**Cause**: feedback wire points to the AND-Gate, which emits that string when blocked.

**Fix**: wire feedback from the Synthesizer (or any node that always produces real content).

### Epsilon too high for your topology

**Symptom**: circuit exits after 1 iteration even though output quality is low.

**Cause**: `aggregate_delta` is diluted by constant-output nodes (Sink always emits ZERO). In a 5-node circuit with 1 active Motor, the Motor's real delta is divided by 5 in the aggregate.

**Fix**: use `epsilon` around 0.03–0.05. For circuits with many passive nodes, go lower (0.01).

### AND-Gate threshold above 0.6

**Symptom**: gate never passes; motors can't produce high enough confidence on iterative tasks.

**Fix**: lower threshold to 0.45–0.55. Use `early_exit_threshold: 0.85` for the "done fast when clear" case.

### Redundant Resistor

If a Resistor's `threshold` equals the downstream AND-Gate's `threshold`, the Resistor adds nothing — the gate already rejects any input below its own threshold. Only use a Resistor when you want to raise the bar for one specific input *above* the general gate threshold.
