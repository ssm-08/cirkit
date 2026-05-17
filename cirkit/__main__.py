"""CLI: python -m cirkit run <json_path> "<user_prompt>" """
import sys
import cirkit  # triggers all registrations


def main():
    if len(sys.argv) < 4 or sys.argv[1] != "run":
        print('Usage: python -m cirkit run <circuit.json> "<user prompt>"', file=sys.stderr)
        sys.exit(1)

    json_path = sys.argv[2]
    user_prompt = sys.argv[3]

    try:
        circuit = cirkit.load_circuit(json_path)
    except (ValueError, FileNotFoundError) as e:
        print(f"Error loading circuit: {e}", file=sys.stderr)
        sys.exit(1)

    def _on_iter(it, delta, node_info):
        print(f"[iter {it}, delta={delta:.4f}]", flush=True)
        for nid, info in node_info.items():
            k = 1 if info["cached"] else 0
            print(f"[node {nid} c={info['conf']:.4f} x={info['contra']:.4f} k={k}]", flush=True)

    result = cirkit.run(circuit, user_prompt, on_iter=_on_iter)

    final_delta = result.delta_history[-1] if result.delta_history else 0.0
    if result.converged:
        print(f"[converged after {result.iterations} iter, final delta={final_delta:.4f}]")
    else:
        print(f"[MAX_ITER (non-convergent) after {result.iterations} iter, final delta={final_delta:.4f}]")

    print(result.output.content)


if __name__ == "__main__":
    main()
