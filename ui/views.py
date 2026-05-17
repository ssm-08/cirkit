import json
import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from django.http import StreamingHttpResponse, JsonResponse, FileResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET

sys.path.insert(0, str(Path(__file__).parent))
from circuit_utils import validate_circuit, parse_cirkit_line

UI_HTML = Path(__file__).parent / "index.html"


@require_GET
def circuit_page(request):
    """GET /cirkit/  ->  serves ui/index.html"""
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

    clean_circuit = _strip_ui_fields(circuit)

    response = StreamingHttpResponse(
        _stream_cirkit(clean_circuit, prompt),
        content_type="text/event-stream",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


@csrf_exempt
@require_POST
def validate_circuit_view(request):
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

    errors = validate_circuit(circuit)
    return JsonResponse({"valid": len(errors) == 0, "errors": errors})


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _strip_ui_fields(circuit: dict) -> dict:
    stripped = dict(circuit)
    stripped["nodes"] = [
        {k: v for k, v in n.items() if k not in ("x", "y", "selected")}
        for n in circuit.get("nodes", [])
    ]
    return stripped


def _stream_cirkit(circuit: dict, prompt: str):
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json.dump(circuit, f, indent=2)
        tmp_path = f.name

    proc = None
    try:
        env = os.environ.copy()
        cirkit_root = os.environ.get("CIRKIT_ROOT", "")
        if cirkit_root:
            env["PYTHONPATH"] = cirkit_root + os.pathsep + env.get("PYTHONPATH", "")

        proc = subprocess.Popen(
            [sys.executable, "-m", "cirkit", "run", tmp_path, prompt],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )

        stderr_lines = []
        stderr_thread = threading.Thread(
            target=lambda: stderr_lines.extend(
                l.rstrip("\n") for l in proc.stderr if l.strip()
            )
        )
        stderr_thread.start()

        output_lines = []
        for raw_line in proc.stdout:
            line = raw_line.rstrip("\n")
            ev = parse_cirkit_line(line)
            if ev is not None:
                yield _sse(ev)
            else:
                output_lines.append(line)

        content = "\n".join(output_lines).strip()
        if content:
            yield _sse({"type": "output", "content": content})

        stderr_thread.join()
        for err_line in stderr_lines:
            yield _sse({"type": "error", "message": err_line})

    except FileNotFoundError:
        yield _sse({
            "type":    "error",
            "message": "cirkit not found — make sure `python -m cirkit` works "
                       "and CIRKIT_ROOT is set if using a local checkout.",
        })
    finally:
        if proc is not None:
            try:
                proc.kill()
            except OSError:
                pass
            proc.wait()
        Path(tmp_path).unlink(missing_ok=True)


def _sse(data: dict) -> str:
    return json.dumps(data) + "\n"
