# Django Integration

CirKit ships a Django view layer (`ui/views.py` + `ui/urls.py`) that serves the canvas and streams circuit execution via `StreamingHttpResponse`.

## Setup

### 1. Copy or mount the ui module

Place `ui/views.py` and `ui/urls.py` in a Django app (e.g., `cirkit_app/`):

```
my_django_project/
  cirkit_app/
    views.py    ← from ui/views.py
    urls.py     ← from ui/urls.py
```

### 2. Set CIRKIT_ROOT

The views import the `cirkit` package via subprocess. Set `CIRKIT_ROOT` in your environment (or Django settings) to the directory containing the `cirkit/` package:

```bash
export CIRKIT_ROOT=/path/to/cirkit-repo
```

Or in `settings.py`:

```python
import os
os.environ.setdefault("CIRKIT_ROOT", "/path/to/cirkit-repo")
```

### 3. Include the URL patterns

In your project's `urls.py`:

```python
from django.urls import path, include

urlpatterns = [
    path("cirkit/", include("cirkit_app.urls")),
    # ...
]
```

This mounts three routes:

| Method | Path | Handler |
|--------|------|---------|
| `GET` | `/cirkit/` | Serves `ui/index.html` |
| `POST` | `/cirkit/run/` | Streams circuit execution (ndjson) |
| `POST` | `/cirkit/validate/` | Validates circuit JSON (returns error list) |

## How streaming works

`run_circuit` in `views.py` receives a circuit JSON body, validates it via `circuit_utils.validate_circuit()`, then spawns `python -m cirkit run <circuit_file> <prompt>` as a subprocess. Stdout lines are parsed and yielded as ndjson events via `StreamingHttpResponse`.

Event types streamed to the browser:

| Event type | Fields | Description |
|------------|--------|-------------|
| `iter` | `iter`, `delta` | End of one iteration |
| `node` | `id`, `conf`, `contra`, `cached` | Per-node status update |
| `output` | `content` | Final circuit output text |
| `done` | `converged`, `iter`, `delta` | Run complete |
| `error` | `message` | Subprocess or validation error |

## Validation

The `validate_circuit` view calls `circuit_utils.validate_circuit()` before running and returns `HTTP 400` with a JSON error list on failure:

```json
{"errors": ["Node 'gate': and_gate requires 'threshold' in config"]}
```

The canvas sends a validation request before every run — if validation fails, the run never starts.

## UI-only fields

The canvas stores node position (`x`, `y`) and display label in the circuit JSON. `views.py` strips these fields via `_strip_ui_fields()` before passing the circuit to the engine, so the engine never sees UI-only data.

## CSRF

The run and validate views are decorated with `@csrf_exempt`. If your Django project requires CSRF protection for all POST routes, handle authentication at the network level (e.g., internal-only deployment, session middleware that pre-validates).

## Standalone server vs. Django

For local development, `ui/server.py` is simpler — no Django required. Use the Django integration for production deployments where the canvas is embedded in a larger Django application.
