import json
import subprocess
import tempfile
import os
from pathlib import Path

from django.http import StreamingHttpResponse, JsonResponse, FileResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET

UI_HTML = Path(__file__).parent / "index.html"


@require_GET
def circuit_page(request):
    """GET /cirkit/  →  serves ui/index.html"""
    return FileResponse(UI_HTML.open("rb"), content_type="text/html; charset=utf-8")


@csrf_exempt
@require_POST
def run_circuit(request):
    """
    POST /cirkit/run/
    Body: { "circuit": { ...cirkit JSON... }, "prompt": "..." }

    Streams back newline-delimited JSON events:
      { "type": "iter",   "iter": 1, "delta": 0.4821, "message": "..." }
      { "type": "output", "content": "..." }
      { "type": "done",   "converged": true, "iter": 3, "delta": 0.0041 }
      { "type": "error",  "message": "..." }
    """
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    circuit = body.get("circuit")
    prompt  = body.get("prompt", "")

    if not circuit or not prompt:
        return JsonResponse({"error": "circuit and prompt are required"}, status=400)

    # Inject node positions into circuit JSON as comments aren't allowed —
    # positions are UI-only so we strip them before passing to cirkit
    clean_circuit = _strip_ui_fields(circuit)

    response = StreamingHttpResponse(
        _stream_cirkit(clean_circuit, prompt),
        content_type="text/event-stream",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"   # disable nginx buffering if present
    return response


@csrf_exempt
@require_POST
def validate_circuit(request):
    """
    POST /cirkit/validate/
    Body: { "circuit": { ...cirkit JSON... } }

    Returns: { "valid": true } or { "valid": false, "errors": [...] }
    """
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    circuit = body.get("circuit")
    if not circuit:
        return JsonResponse({"error": "circuit is required"}, status=400)

    errors = _validate(circuit)
    return JsonResponse({"valid": len(errors) == 0, "errors": errors})


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _strip_ui_fields(circuit: dict) -> dict:
    """Remove x/y/ui keys that the canvas adds but cirkit doesn't understand."""
    stripped = dict(circuit)
    stripped["nodes"] = [
        {k: v for k, v in n.items() if k not in ("x", "y", "selected")}
        for n in circuit.get("nodes", [])
    ]
    return stripped


def _stream_cirkit(circuit: dict, prompt: str):
    """
    Write circuit JSON to a temp file, call `python -m cirkit run`,
    and yield SSE-style newline-delimited JSON lines as they arrive.
    """
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json.dump(circuit, f, indent=2)
        tmp_path = f.name

    try:
        cmd = ["python", "-m", "cirkit", "run", tmp_path, prompt]

        # CIRKIT_ROOT lets you point at a non-installed local checkout
        env = os.environ.copy()
        cirkit_root = os.environ.get("CIRKIT_ROOT", "")
        if cirkit_root:
            env["PYTHONPATH"] = cirkit_root + os.pathsep + env.get("PYTHONPATH", "")

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )

        output_lines = []
        converged    = False
        final_delta  = None
        final_iter   = None

        for raw_line in proc.stdout:
            line = raw_line.rstrip("\n")

            # CirKit convergence header  →  [converged after N iter, final delta=0.XXXX]
            if line.startswith("[converged") or line.startswith("[MAX_ITER"):
                converged   = "converged after" in line
                final_iter  = _parse_int_after(line, "after ")
                final_delta = _parse_float_after(line, "delta=")
                event = {
                    "type":      "done",
                    "converged": converged,
                    "iter":      final_iter,
                    "delta":     final_delta,
                }
                yield _sse(event)

            # Stderr-forwarded iteration lines  →  [iter N] delta=X.XXXX  message
            elif line.startswith("[iter"):
                iter_num = _parse_int_after(line, "[iter ")
                delta    = _parse_float_after(line, "delta=")
                msg      = line.split("]", 1)[-1].strip() if "]" in line else line
                event = {
                    "type":    "iter",
                    "iter":    iter_num,
                    "delta":   delta,
                    "message": msg,
                }
                yield _sse(event)

            else:
                # Accumulate as final output content
                output_lines.append(line)

        # Flush remaining stdout as output event
        content = "\n".join(output_lines).strip()
        if content:
            yield _sse({"type": "output", "content": content})

        # Capture and forward any stderr as error events
        stderr_out = proc.stderr.read().strip()
        if stderr_out:
            for err_line in stderr_out.splitlines():
                if err_line.strip():
                    yield _sse({"type": "error", "message": err_line})

        proc.wait()

    except FileNotFoundError:
        yield _sse({
            "type":    "error",
            "message": "cirkit not found — make sure `python -m cirkit` works "
                       "and CIRKIT_ROOT is set if using a local checkout.",
        })
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def _sse(data: dict) -> str:
    return json.dumps(data) + "\n"


def _parse_int_after(s: str, marker: str) -> int | None:
    try:
        rest = s.split(marker, 1)[1]
        return int(rest.split()[0].rstrip(","))
    except (IndexError, ValueError):
        return None


def _parse_float_after(s: str, marker: str) -> float | None:
    try:
        rest = s.split(marker, 1)[1]
        return float(rest.split("]")[0].split()[0])
    except (IndexError, ValueError):
        return None


def _validate(circuit: dict) -> list[str]:
    errors = []
    cfg = circuit.get("config", {})
    eps = cfg.get("epsilon")
    if eps is None or not (0 < eps <= 1.0):
        errors.append("config.epsilon must be in (0, 1.0]")
    if not isinstance(cfg.get("max_iter"), int) or cfg["max_iter"] < 1:
        errors.append("config.max_iter must be an integer >= 1")

    nodes = {n["id"]: n for n in circuit.get("nodes", [])}
    if len(nodes) != len(circuit.get("nodes", [])):
        errors.append("Duplicate node IDs found")

    sink_id = circuit.get("sink")
    if not sink_id:
        errors.append("sink is required")
    elif sink_id not in nodes:
        errors.append(f"sink '{sink_id}' does not exist in nodes")

    valid_roles = {"context", "peer", "feedback"}
    for w in circuit.get("wires", []):
        if w.get("from") not in nodes:
            errors.append(f"Wire from unknown node '{w.get('from')}'")
        if w.get("to") not in nodes:
            errors.append(f"Wire to unknown node '{w.get('to')}'")
        role = w.get("role", "context")
        if role not in valid_roles:
            errors.append(f"Unknown wire role '{role}' — must be context/peer/feedback")

    return errors
