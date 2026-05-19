from cirkit.graph import Circuit
from cirkit.state import RunState, RunResult
from cirkit.signal import Signal
from cirkit.convergence import aggregate_delta
from cirkit.nodes.battery import Battery


def run(circuit: Circuit, user_prompt: str, epsilon: float = None, max_iter: int = None, on_iter=None) -> RunResult:
    """Synchronous Jacobi update loop.

    Phases:
    A. Initialize RunState (all outputs = Signal.ZERO)
    B. Inject user_prompt into Battery node_state dicts
    C. R9 Bootstrap: run input-less nodes once before iter 0
    D. Main loop (Jacobi): read prev_outputs snapshot, update all nodes, compute delta
       - R10: check convergence from iter 0 (no it>0 gate)
       - R4: early-exit on consensus_locked AND sink has positive-confidence last_input (G14 guard)
    E. Extract sink last_input as final output

    Non-convergence returns RunResult(converged=False), never raises.
    """
    if epsilon is None:
        epsilon = circuit.config.get("epsilon", 0.05)
    if max_iter is None:
        max_iter = circuit.config.get("max_iter", 10)

    state = RunState()
    state.outputs = {nid: Signal.ZERO for nid in circuit.nodes}
    state.node_state = {nid: {} for nid in circuit.nodes}

    # B. Inject user_prompt into Battery node states before bootstrap
    for nid, node in circuit.nodes.items():
        if isinstance(node, Battery):
            state.node_state[nid]["user_prompt"] = user_prompt

    # C. Bootstrap: seed input-less nodes once before iter 0
    for nid, node in circuit.nodes.items():
        if not circuit.in_edges.get(nid):
            state.outputs[nid] = node._maybe_cached_step({}, state.node_state[nid])

    converged = False

    for it in range(max_iter):
        state.iteration = it
        prev_outputs = dict(state.outputs)

        new_outputs = {}
        for nid, node in circuit.nodes.items():
            grouped: dict[str, list[Signal]] = {}
            for src_id, role_or_branch in circuit.in_edges.get(nid, []):
                is_branch_wire = (src_id, nid) in circuit.branch_wire_pairs
                if is_branch_wire:
                    signal = circuit.nodes[src_id].get_branch_output(
                        role_or_branch, state.node_state[src_id]
                    )
                    role = "context"
                else:
                    signal = prev_outputs[src_id]
                    role = role_or_branch
                grouped.setdefault(role, []).append(signal)

            new_outputs[nid] = node._maybe_cached_step(grouped, state.node_state[nid])

        miss = {n for n in new_outputs if new_outputs[n] is not prev_outputs[n]}
        agg = (
            aggregate_delta(
                {n: prev_outputs[n] for n in miss},
                {n: new_outputs[n] for n in miss},
            )
            if miss else 0.0
        )
        state.outputs = new_outputs
        state.delta_history.append(agg)

        if on_iter is not None:
            node_info = {
                nid: {
                    "conf":   new_outputs[nid].confidence,
                    "contra": new_outputs[nid].contradiction,
                    "cached": new_outputs[nid] is prev_outputs[nid],
                }
                for nid in circuit.nodes
            }
            on_iter(it + 1, agg, node_info)

        # R10: convergence check from iter 0
        if agg < epsilon:
            converged = True
            break


    final = state.node_state[circuit.sink_id].get("last_input", Signal.ZERO)

    return RunResult(
        output=final,
        iterations=state.iteration + 1,
        converged=converged,
        delta_history=state.delta_history,
        all_outputs=state.outputs,
    )
