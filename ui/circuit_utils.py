"""Shared circuit utilities for server.py (stdlib) and views.py (Django)."""
from __future__ import annotations


def validate_circuit(circuit: dict) -> list[str]:
    errors = []
    cfg = circuit.get("config", {})
    eps = cfg.get("epsilon")
    if eps is None or not (0 < eps <= 1.0):
        errors.append("config.epsilon must be in (0, 1.0]")
    if not isinstance(cfg.get("max_iter"), int) or cfg["max_iter"] < 1:
        errors.append("config.max_iter must be an integer >= 1")

    node_list = circuit.get("nodes", [])
    nodes = {n["id"]: n for n in node_list}
    if len(nodes) != len(node_list):
        errors.append("Duplicate node IDs")

    sink_id = circuit.get("sink")
    if not sink_id:
        errors.append("sink is required")
    elif sink_id not in nodes:
        errors.append(f"sink '{sink_id}' not in nodes")

    valid_roles = {"context", "peer", "feedback"}
    for w in circuit.get("wires", []):
        if w.get("from") not in nodes:
            errors.append(f"wire from unknown '{w.get('from')}'")
        if w.get("to") not in nodes:
            errors.append(f"wire to unknown '{w.get('to')}'")
        role = w.get("role", "context")
        if role not in valid_roles:
            errors.append(f"bad role '{role}'")

    return errors


def parse_int_after(s: str, marker: str) -> int | None:
    try:
        return int(s.split(marker, 1)[1].split()[0].rstrip(","))
    except (IndexError, ValueError):
        return None


def parse_float_after(s: str, marker: str) -> float | None:
    try:
        return float(s.split(marker, 1)[1].split("]")[0].split()[0])
    except (IndexError, ValueError):
        return None


def parse_cirkit_line(line: str) -> dict | None:
    """Parse a cirkit CLI stdout line -> event dict, or None if it's output content."""
    if line.startswith("[converged") or line.startswith("[MAX_ITER"):
        return {
            "type": "done",
            "converged": "converged after" in line,
            "iter": parse_int_after(line, "after "),
            "delta": parse_float_after(line, "delta="),
        }
    if line.startswith("[iter"):
        return {
            "type": "iter",
            "iter": parse_int_after(line, "[iter "),
            "delta": parse_float_after(line, "delta="),
            "message": line.split("]", 1)[-1].strip(),
        }
    if line.startswith("[node "):
        # [node <id> c=X.XXXX x=Y.YYYY k=0|1]
        parts = line[6:].rstrip("]").split()
        nid = parts[0]
        conf = contra = 0.0
        cached = False
        for p in parts[1:]:
            if p.startswith("c="):
                try: conf = float(p[2:])
                except ValueError: pass
            elif p.startswith("x="):
                try: contra = float(p[2:])
                except ValueError: pass
            elif p == "k=1":
                cached = True
        return {"type": "node", "id": nid, "conf": conf, "contra": contra, "cached": cached}
    return None
