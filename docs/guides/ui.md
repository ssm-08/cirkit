# UI Canvas

The CirKit canvas is a standalone single-file app (`ui/index.html`) with no build step and no runtime dependencies beyond Google Fonts.

## Starting the dev server

```bash
python ui/server.py           # default port 8080
python ui/server.py 9000      # custom port
```

Open `http://localhost:8080` in your browser. The server sets `PYTHONPATH` to the project root automatically, so `cirkit` is importable without `pip install -e .`.

## Demo mode

If the server isn't running, the canvas detects the unreachable `/cirkit/validate/` endpoint and falls back to **demo mode**: a 4-iteration simulation with pre-seeded node outputs. All UI features work in demo mode — it's useful for exploring the interface without a backend.

## Building a circuit

### Place nodes

Drag a node type from the left palette onto the canvas. Node types: Battery, Motor, Resistor, AND-Gate, Router, Sink.

Click a placed node to open its inspector on the right. Configure it:

- **Battery**: set `content` (the task description / system prompt prefix)
- **Motor**: set `system` (the LLM system prompt; must end with a confidence instruction)
- **Resistor / AND-Gate**: set `threshold` (0.0–1.0)
- **Router**: set `rule` and add branch definitions
- **Sink**: no config required

### Draw wires

Hover a node to reveal its output port (bottom). Drag from the port to another node to create a wire. A role picker appears — select `context`, `peer`, or `feedback`. Router output wires use `branch` names instead.

Click an existing wire to select it. The inspector switches to wire mode: change the role from the dropdown or delete the wire.

### Wire role colors

| Role | Color | Style |
|------|-------|-------|
| `context` | Gray / steel-blue | Solid |
| `peer` | Teal | Solid |
| `feedback` | Amber | Dashed |

### Zoom and pan

- **Mouse wheel** over canvas: zoom in/out
- **+/−/⌂ buttons** (bottom-left overlay): zoom in, out, reset to 100%
- Range: 25%–250%

All coordinate math is zoom-aware — wire endpoints and node positions stay aligned at any zoom level.

### Resize panels

- Drag the 4px handle on the right edge of the palette to resize it (120–400px)
- Drag the 4px handle on the left edge of the inspector to resize it (120–400px)
- Drag the handle on the top edge of the output drawer to resize it (60–500px)

## Running a circuit

Click **RUN**. The button becomes **STOP** while running. The canvas and palette lock (dimmed, pointer-events disabled) during a run to prevent mid-run edits.

Validation runs before the circuit starts. If the circuit is invalid, errors appear and the button re-enables immediately.

During a run:

- **Status bar** shows iteration count, delta, and elapsed time (updated every 100ms)
- **Node cards** update live: confidence (`c=`), contradiction, cached indicator
- When a node's `step()` is called (not cached), it flashes **FIRE** for 220ms
- **Signal pulses** animate along wires, colored by role

Click **STOP** to abort mid-run.

## Output drawer

The output drawer (bottom panel) has three tabs:

- **LOG** — per-iteration status lines (`[iter N, delta=X]`, per-node metrics)
- **OUTPUT** — the circuit's final output text
- **JSON** — the raw circuit JSON (editable export)

Tabs are persistent — switching tabs doesn't clear content.

## Exporting and importing

The **JSON** tab shows the current circuit as JSON. Copy it to save your circuit. Paste into the JSON tab and click **Load** to restore a circuit.

## Django integration

To embed the canvas in a Django project, see the [Django Integration guide](django.md). The canvas makes requests to `/cirkit/validate/` and `/cirkit/run/` — these routes are provided by `ui/views.py`.
