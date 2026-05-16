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

    epsilon = circuit.config.get("epsilon", 0.05)
    max_iter = circuit.config.get("max_iter", 10)

    result = cirkit.run(circuit, user_prompt, epsilon=epsilon, max_iter=max_iter)

    if result.converged:
        print(f"[converged after {result.iterations} iter, final delta={result.delta_history[-1]:.4f}]")
    else:
        print(f"[MAX_ITER (non-convergent) after {result.iterations} iter, final delta={result.delta_history[-1]:.4f}]")

    print(result.output.content)


if __name__ == "__main__":
    main()
