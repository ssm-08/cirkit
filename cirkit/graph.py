from __future__ import annotations
import json
from dataclasses import dataclass, field

from cirkit.nodes.battery import Battery
from cirkit.nodes.sink import Sink
from cirkit.nodes.router import Router


@dataclass
class Wire:
    from_id: str
    to_id: str
    role: str = "context"       # mutually exclusive with branch; one of context|feedback|peer
    branch: str | None = None   # ONLY for Router-originating wires


@dataclass
class Circuit:
    nodes: dict                          # node_id -> Node instance
    wires: list                          # list[Wire]
    sink_id: str
    config: dict                         # epsilon, max_iter
    in_edges: dict = field(default_factory=dict)   # node_id -> list[(src_id, role_or_branch)]
    out_edges: dict = field(default_factory=dict)  # node_id -> list[(dst_id, role_or_branch)]
    branch_wire_pairs: set = field(default_factory=set)  # set of (from_id, to_id) that are branch wires


def _check_structural_cycles(nodes: dict, wires: list) -> None:
    """Raise ValueError if non-feedback wires form a directed cycle.

    Feedback-role wires are intentional Jacobi back-edges and are excluded.
    Uses iterative DFS (no recursion limit risk).
    """
    fwd: dict[str, list[str]] = {nid: [] for nid in nodes}
    for wire in wires:
        if wire.role != "feedback":
            fwd[wire.from_id].append(wire.to_id)

    WHITE, GRAY, BLACK = 0, 1, 2
    color = {nid: WHITE for nid in nodes}

    for start in list(nodes):
        if color[start] != WHITE:
            continue
        stack = [(start, iter(fwd[start]))]
        color[start] = GRAY
        while stack:
            nid, children = stack[-1]
            try:
                child = next(children)
                if color[child] == GRAY:
                    raise ValueError(
                        f"Circuit has a structural cycle: '{nid}' → '{child}' "
                        f"(use role='feedback' for intentional back-edges)"
                    )
                if color[child] == WHITE:
                    color[child] = GRAY
                    stack.append((child, iter(fwd[child])))
            except StopIteration:
                color[nid] = BLACK
                stack.pop()


def load_circuit(path: str) -> Circuit:
    """Load + validate JSON circuit definition."""
    from cirkit.nodes import NODE_REGISTRY

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    cfg = data.get("config", {})
    epsilon = cfg.get("epsilon", 0.05)
    max_iter = cfg.get("max_iter", 10)

    if not (0 < epsilon <= 1.0):
        raise ValueError(f"epsilon must be in (0, 1.0], got {epsilon}")
    if max_iter < 1:
        raise ValueError(f"max_iter must be >= 1, got {max_iter}")

    sink_id = data["sink"]

    nodes = {}
    for node_data in data["nodes"]:
        nid = node_data["id"]
        if nid in nodes:
            raise ValueError(f"Duplicate node id: {nid}")
        ntype = node_data["type"]
        if ntype not in NODE_REGISTRY:
            raise ValueError(f"Unknown node type '{ntype}'. Valid: {sorted(NODE_REGISTRY.keys())}")
        nodes[nid] = NODE_REGISTRY[ntype](node_data.get("config", {}))

    if sink_id not in nodes:
        raise ValueError(f"sink '{sink_id}' not in nodes")
    if not isinstance(nodes[sink_id], Sink):
        raise ValueError(f"sink node '{sink_id}' must have type 'sink'")

    valid_roles = {"context", "feedback", "peer"}
    wires = []
    branch_wire_pairs = set()

    for w in data.get("wires", []):
        from_id = w["from"]
        to_id = w["to"]
        if from_id not in nodes:
            raise ValueError(f"Wire from unknown node '{from_id}'")
        if to_id not in nodes:
            raise ValueError(f"Wire to unknown node '{to_id}'")

        is_router_src = isinstance(nodes[from_id], Router)
        has_branch = "branch" in w
        has_role = "role" in w

        if is_router_src and not has_branch:
            raise ValueError(f"Wire from Router '{from_id}' must have 'branch' field")
        if not is_router_src and has_branch:
            raise ValueError(f"Wire from non-Router '{from_id}' must not have 'branch' field")

        role = w.get("role", "context")
        branch = w.get("branch")

        if not has_branch and role not in valid_roles:
            raise ValueError(f"Wire role '{role}' must be one of {valid_roles}")

        wire = Wire(from_id=from_id, to_id=to_id, role=role, branch=branch)
        wires.append(wire)
        if has_branch:
            branch_wire_pairs.add((from_id, to_id))

    for nid, node in nodes.items():
        if isinstance(node, Router):
            declared = {b["branch"] for b in node.branches}
            wired = {w.branch for w in wires if w.from_id == nid}
            for b in wired:
                if b not in declared:
                    raise ValueError(f"Router '{nid}' wire branch '{b}' not in config branches")
            defaults = [b for b in node.branches if b.get("default")]
            if len(defaults) != 1:
                raise ValueError(f"Router '{nid}' must have exactly one default branch")

    sink_out = [w for w in wires if w.from_id == sink_id]
    if sink_out:
        raise ValueError(f"Sink '{sink_id}' must have no out-edges")

    _check_structural_cycles(nodes, wires)

    in_edges = {nid: [] for nid in nodes}
    out_edges = {nid: [] for nid in nodes}
    for wire in wires:
        role_or_branch = wire.branch if wire.branch else wire.role
        in_edges[wire.to_id].append((wire.from_id, role_or_branch))
        out_edges[wire.from_id].append((wire.to_id, role_or_branch))

    return Circuit(
        nodes=nodes, wires=wires, sink_id=sink_id, config=cfg,
        in_edges=in_edges, out_edges=out_edges, branch_wire_pairs=branch_wire_pairs
    )
