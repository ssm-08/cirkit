# Roadmap

Known gaps and directions for future development, roughly ordered by scope.

---

## Near-term

### Or-Gate and XOR-Gate

The UI canvas already shows Or-Gate and XOR-Gate as greyed-out placeholders. Both need engine implementations:

- **Or-Gate**: passes when *any* input exceeds the threshold, vs AND-Gate requiring all. Useful for "first responder" patterns where the fastest good-enough answer wins, or where any one reviewer approving is sufficient.
- **XOR-Gate**: passes only when exactly one input exceeds threshold. Useful for mutually exclusive branches — emit whichever specialist produced the confident answer, suppress the rest.

### Per-motor LLM provider config

Motor currently always calls `claude -p`. A `provider` config field on the Motor would allow different motors in the same circuit to use different CLI backends (`openai`, `gemini`, a local ollama wrapper) without any engine changes. The only contract is: read assembled prompt from stdin, write output + confidence JSON to stdout.

### Typed wire content

Wires carry `Signal.content` as untyped strings. A `content_type` field on the wire (`markdown`, `json_object`, `code:python`) could be validated on arrival and advertised to the receiving node so it doesn't have to guess format. This catches misrouted signals early and enables downstream parsers to be less defensive.

---

## Medium-term

### Async motor execution

Within a single iteration, all nodes are stepped sequentially. Because Jacobi update means every node reads from the *previous* iteration's snapshot, nodes within one iteration are fully independent and could run concurrently. Async execution would reduce wall-clock time per iteration from `O(n × llm_latency)` to approximately `O(llm_latency)` for fully parallel circuits.

### Streaming motor output

`call_claude()` currently waits for the full LLM response before returning. Streaming would let the UI show partial content as it arrives and enable early termination — once `{"confidence": X}` appears in the stream, the motor has reported its confidence and generation could stop.

### Circuit persistence and resume

Long-running circuits (many motors, many iterations) have no checkpointing. Serializable `RunState` snapshots would allow resuming an interrupted run from the last completed iteration — useful for multi-stage workflows where mid-run failures are expensive to restart from scratch.

---

## Longer-term

### Motor tool use

Motor could expose Claude's tool-use API to let LLM nodes call external functions (web search, code execution, database queries, file reads) as part of their step. Tool results would feed back into the same iteration's assembled prompt, making each Motor step a mini-agentic loop within the outer circuit loop.

### Visual step-through debugger

A step-through mode in the UI canvas: pause after each iteration, inspect per-node signal state (content, confidence, flags), manually override signal values or confidence, then resume. Useful for understanding why a circuit oscillates or converges prematurely without having to add logging to Python code.

### Circuit composition

Allow a circuit file to embed another circuit as a single "macro-node." The sub-circuit would expose its Battery inputs and Sink output as external ports. This enables reusing well-tuned sub-circuits (a validated reviewer + gate + synthesizer module, for example) across different top-level circuits without copy-pasting JSON.

### Multi-sink output

Currently circuits have exactly one Sink that determines the output. Multi-sink support would let a circuit expose multiple named outputs — for example, a code review circuit could separately surface the security analysis, the correctness analysis, and the synthesized recommendation as distinct outputs rather than concatenating everything into one.
