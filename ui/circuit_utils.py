"""Shared circuit utilities for server.py (stdlib) and views.py (Django)."""
from __future__ import annotations

VALID_ROLES = {"context", "peer", "feedback"}
ROUTER_RULES = {"by_confidence", "by_content_length", "by_flag"}


def validate_circuit(circuit: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(circuit, dict):
        return ["circuit must be an object"]

    cfg = circuit.get("config", {})
    eps = cfg.get("epsilon")
    if eps is None or not isinstance(eps, (int, float)) or not (0 < eps <= 1.0):
        errors.append("config.epsilon must be in (0, 1.0]")
    max_iter = cfg.get("max_iter")
    if not isinstance(max_iter, int) or max_iter < 1:
        errors.append("config.max_iter must be an integer >= 1")

    node_list = circuit.get("nodes", [])
    if not isinstance(node_list, list):
        return errors + ["nodes must be a list"]

    nodes: dict[str, dict] = {}
    for i, node in enumerate(node_list):
        if not isinstance(node, dict):
            errors.append(f"node {i} must be an object")
            continue
        nid = node.get("id")
        ntype = node.get("type")
        if not nid:
            errors.append(f"node {i} missing id")
            continue
        if nid in nodes:
            errors.append(f"Duplicate node ID '{nid}'")
        nodes[nid] = node
        if not ntype:
            errors.append(f"node '{nid}' missing type")

    sink_id = circuit.get("sink")
    if not sink_id:
        errors.append("sink is required")
    elif sink_id not in nodes:
        errors.append(f"sink '{sink_id}' not in nodes")
    elif nodes[sink_id].get("type") != "sink":
        errors.append(f"sink node '{sink_id}' must have type 'sink'")

    for nid, node in nodes.items():
        ntype = node.get("type")
        cfg = node.get("config", {})
        if ntype == "router":
            errors.extend(_validate_router(nid, cfg))
        elif ntype == "battery":
            if "content" not in cfg:
                errors.append(f"battery '{nid}' config requires 'content'")
        elif ntype in ("and_gate", "resistor"):
            if "threshold" not in cfg:
                errors.append(f"{ntype} '{nid}' config requires 'threshold'")

    wires = circuit.get("wires", [])
    if not isinstance(wires, list):
        return errors + ["wires must be a list"]

    for i, wire in enumerate(wires):
        if not isinstance(wire, dict):
            errors.append(f"wire {i} must be an object")
            continue
        from_id = wire.get("from")
        to_id = wire.get("to")
        if from_id not in nodes:
            errors.append(f"wire from unknown '{from_id}'")
        if to_id not in nodes:
            errors.append(f"wire to unknown '{to_id}'")
            continue
        if from_id == sink_id:
            errors.append(f"sink '{sink_id}' must have no out-edges")

        is_router = from_id in nodes and nodes[from_id].get("type") == "router"
        has_branch = "branch" in wire
        if is_router:
            branch = wire.get("branch")
            branches = _router_branch_names(nodes[from_id].get("config", {}))
            if not branch:
                errors.append(f"wire from Router '{from_id}' must have branch")
            elif branch not in branches:
                errors.append(f"Router '{from_id}' wire branch '{branch}' not in config branches")
        elif has_branch:
            errors.append(f"wire from non-Router '{from_id}' must not have branch")
        else:
            role = wire.get("role", "context")
            if role not in VALID_ROLES:
                errors.append(f"bad role '{role}'")

    return errors


def _validate_router(nid: str, cfg: dict) -> list[str]:
    errors: list[str] = []
    if cfg.get("rule") not in ROUTER_RULES:
        errors.append(f"Router '{nid}' rule must be one of {sorted(ROUTER_RULES)}")

    branches = cfg.get("branches")
    if not isinstance(branches, list) or not branches:
        return errors + [f"Router '{nid}' must define branches"]

    names: set[str] = set()
    defaults = 0
    for i, branch in enumerate(branches):
        if not isinstance(branch, dict) or not branch.get("branch"):
            errors.append(f"Router '{nid}' branch {i} missing branch name")
            continue
        name = branch["branch"]
        if name in names:
            errors.append(f"Router '{nid}' duplicate branch '{name}'")
        names.add(name)
        if branch.get("default"):
            defaults += 1
    if defaults != 1:
        errors.append(f"Router '{nid}' must have exactly one default branch")
    return errors


def _router_branch_names(cfg: dict) -> set[str]:
    return {b.get("branch") for b in cfg.get("branches", []) if isinstance(b, dict)}


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
    if line.startswith("[cost "):
        tokens_in = parse_int_after(line, "tokens_in=")
        tokens_out = parse_int_after(line, "tokens_out=")
        cost_usd = parse_float_after(line, "cost_usd=$")
        return {"type": "cost", "tokens_in": tokens_in, "tokens_out": tokens_out, "cost_usd": cost_usd}
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
        parts = line[6:].rstrip("]").split()
        nid = parts[0]
        conf = contra = 0.0
        cached = False
        for p in parts[1:]:
            if p.startswith("c="):
                try:
                    conf = float(p[2:])
                except ValueError:
                    pass
            elif p.startswith("x="):
                try:
                    contra = float(p[2:])
                except ValueError:
                    pass
            elif p == "k=1":
                cached = True
        return {"type": "node", "id": nid, "conf": conf, "contra": contra, "cached": cached}
    return None
