from cirkit.nodes.base import Node
from cirkit.signal import Signal


class Router(Node):
    """Adaptive-compute branching node (R11).

    One input (role='context'), N named branch outputs.
    Evaluates structured rule config — no eval(), no exec().

    Supported rules (cfg['rule']):
      by_confidence  : branches declare min_confidence; first match wins; default fallback
      by_content_length: branches declare max_length; first match wins; default fallback
      by_flag        : branches declare flag_name; matches if signal.flags.get(flag_name); default fallback

    Stores routing result in state:
      state['routed_branch']  = matched branch name
      state['branch_outputs'] = {branch_name: Signal or Signal.ZERO, ...}

    step() returns Signal.ZERO — engine reads branch outputs via get_branch_output().
    Wires from Router carry 'branch' field naming the target output (not 'role').
    """

    def __init__(self, config: dict):
        self.rule = config["rule"]
        self.branches = config["branches"]

    def step(self, inputs: dict, state: dict) -> Signal:
        signal = inputs.get("context", [Signal.ZERO])[0] if inputs.get("context") else Signal.ZERO

        matched_name = self._match_branch(signal)
        state["routed_branch"] = matched_name

        branch_outputs = {b["branch"]: Signal.ZERO for b in self.branches}
        branch_outputs[matched_name] = signal
        state["branch_outputs"] = branch_outputs

        return Signal.ZERO

    def _match_branch(self, signal: Signal) -> str:
        # Branches evaluated in JSON declaration order; first non-default match wins.
        # Place higher-priority branches before lower-priority ones in the circuit JSON.
        default_name: str | None = None

        if self.rule == "by_confidence":
            for branch in self.branches:
                if branch.get("default"):
                    default_name = branch["branch"]
                elif signal.confidence >= branch["min_confidence"]:
                    return branch["branch"]

        elif self.rule == "by_content_length":
            for branch in self.branches:
                if branch.get("default"):
                    default_name = branch["branch"]
                elif len(signal.content) <= branch["max_length"]:
                    return branch["branch"]

        elif self.rule == "by_flag":
            for branch in self.branches:
                if branch.get("default"):
                    default_name = branch["branch"]
                elif signal.flags.get(branch["flag_name"]):
                    return branch["branch"]

        else:
            raise ValueError(f"Unknown Router rule: {self.rule}")

        if default_name is None:
            raise ValueError(f"Router has no default branch (rule={self.rule})")
        return default_name

    def get_branch_output(self, branch_name: str, state: dict) -> Signal:
        """Engine calls this per Router out-edge to get branch-specific output."""
        return state.get("branch_outputs", {}).get(branch_name, Signal.ZERO)
