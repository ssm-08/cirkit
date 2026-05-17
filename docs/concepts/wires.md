# Wire Roles

Every wire has a `role` that determines how the receiving Motor groups it in its assembled prompt. Wire roles are semantic — they change what the LLM sees, not the engine's graph traversal logic.

## The three roles

### `context`

The task definition or background information. Typically from a Battery.

Motor groups all `context` wires under:

```
[CONTEXT]
<content of context signal>
```

Use `context` for: system instructions, task description, the original user prompt.

### `peer`

Another node's completed output on this iteration. Used for parallel reviewers who need to see each other's work, or for a writer whose output a reviewer must evaluate.

Motor groups all `peer` wires under:

```
[PEER OUTPUTS]
PEER 1: <content>
PEER 2: <content>
```

Use `peer` for: writer → reviewer, reviewer A → reviewer B.

!!! warning "Common mistake"
    In a writer + reviewer circuit, `battery → reviewer` gives the reviewer the task context, but the reviewer cannot see the written content without a separate `writer → reviewer (peer)` wire. Always add this wire or the reviewer has nothing to review.

### `feedback`

The output of a downstream synthesizer (or any node) fed back upstream for refinement on the next iteration.

Motor groups all `feedback` wires under:

```
[FEEDBACK FROM PREVIOUS ITERATION]
<synthesized or critique content>
```

Use `feedback` for: synthesizer → motors, critique → writer.

**Feedback wires bypass cycle detection.** The graph validator runs DFS to detect non-feedback cycles and raises `ValueError` if found. Wires with `role: feedback` are excluded from this check — they represent intentional back-edges that drive iterative refinement.

## AND-Gate and wire roles

AND-Gate collects **all** non-ZERO inputs regardless of role. The role on a motor → gate wire is documentary only — there is no functional difference between `peer` and `context` for gate inputs.

## Router wires

Router out-edges use `branch` instead of `role`:

```json
{"from": "triage", "to": "fast_motor", "branch": "high"}
```

Router wires must NOT also include a `role` field. Including both bypasses cycle detection.

## Wire role color coding in the UI

| Role | Color | Style |
|------|-------|-------|
| `context` | Gray / steel-blue | Solid |
| `peer` | Teal | Solid |
| `feedback` | Amber | Dashed |

Signal pulses animate along wires during a run, colored by role.
