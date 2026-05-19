# Wire Roles

Every wire connects two nodes and carries a **role** label. The role does two things:

1. **Framing** — Motor nodes group incoming signals by role and present them in separate sections of the LLM prompt so the model knows what each input means.
2. **Structure** — `feedback` wires mark intentional back-edges so the cycle validator lets them through.

Non-Motor nodes (AND-Gate, Resistor, Sink, Router) process signals without reading the role — for those nodes, the role label is purely documentary.

---

## How signals travel

All wires carry the **previous iteration's output** — not the current one. Every node reads a frozen snapshot of last iteration's outputs and then produces its new output. This is why iter 1 is often a "warm-up": a motor with a peer wire from a sibling sees `Signal.ZERO` on iter 1 (sibling had no output yet) and only sees real content starting iter 2.

---

## The three roles

### `context`

**Default role. Use for everything that isn't peer output or a back-edge.**

Context is task definition, instructions, or upstream content the receiving node needs to do its job.

```
[CONTEXT]
<content>
```

**Use context for:**

- `battery → motor` — task description and instructions
- `motor → motor` in a sequential pipeline — upstream draft flowing to next stage
- `gate → motor` or `gate → sink` — gate output going downstream
- Any wire where the sender is strictly upstream of the receiver

---

### `peer`

**For Motor-to-Motor sibling awareness.**

Peer wires let one motor see another motor's output when both are working at the same level of a circuit — for example, a reviewer reading a writer's draft, or two motors that need to be mutually aware of each other's work.

```
[PEER OUTPUTS]
PEER 1: <content>
PEER 2: <content>
```

**Use peer for:**

- `writer → reviewer` — reviewer must read the draft to critique it
- `motor_a → motor_b` + `motor_b → motor_a` — bidirectional sibling awareness (two separate wires)

**Peer ≠ bidirectional.** A single peer wire is unidirectional: `writer → reviewer` lets the reviewer see the writer's output, but not vice versa. For mutual awareness, add both directions explicitly.

**Peer has a 1-iteration lag.** On iter 1, a motor with an incoming peer wire sees `Signal.ZERO` from its sibling — the sibling had no output in the previous iteration. Real peer content arrives starting iter 2.

!!! warning "Independent parallel reviewers — no peer wires needed"
    If two motors analyze the same source input independently (e.g. code review + security review of the same PR), they should NOT be wired to each other with `peer`. Each reads directly from the Battery. Adding a peer wire would make one motor's output depend on the other's, which is not what you want for independent parallel analysis.

    Only wire `motor_a → motor_b (peer)` when you explicitly want B to see and respond to A's output.

---

### `feedback`

**For back-edges — wires that flow downstream-to-upstream.**

In iterative refinement circuits, a downstream synthesizer or reviewer sends its output back upstream so motors can refine their work in the next iteration. These wires travel against the normal graph direction (downstream → upstream), which would normally look like a cycle to the validator. The `feedback` role marks them as intentional back-edges, bypassing cycle detection.

```
[FEEDBACK FROM PREVIOUS ITERATION]
<content>
```

**Use feedback for:**

- `synthesizer → motor` — fused result feeding back to upstream reviewers for refinement
- Any wire where the sender is downstream of the receiver in the normal graph flow

**Feedback is structurally required.** Without the `feedback` role, a downstream-to-upstream wire fails graph validation with a cycle error. It isn't optional labeling — it's what makes the back-edge legal.

**Feedback also has a 1-iteration lag**, like all wires. A motor sees feedback from the synthesizer's *previous* iteration output, not the current one.


---

## Which nodes use wire roles

| Node | Uses role? | How |
|------|-----------|-----|
| **Motor** | Yes | Groups inputs into `[CONTEXT]`, `[PEER OUTPUTS]`, `[FEEDBACK]` sections in the LLM prompt |
| **AND-Gate** | No | Collects all non-ZERO inputs regardless of role; role on motor→gate wires is documentary only |
| **Resistor** | No | Single-input pass/block; role ignored |
| **Sink** | No | Selects by confidence; role ignored |
| **Router** | N/A | Uses `branch` field instead of `role` |

---

## Router wires

Router out-edges use `branch` instead of `role`:

```json
{"from": "triage", "to": "fast_motor", "branch": "high"}
```

Router wires must NOT also include a `role` field — having both bypasses cycle detection.

---

## Wire role colors in the UI

| Role | Color | Style |
|------|-------|-------|
| `context` | Gray / steel-blue | Solid |
| `peer` | Teal | Solid |
| `feedback` | Amber | Dashed |

Signal pulses animate along wires during a run, colored by role.
