from cirkit.nodes.base import Node
from cirkit.signal import Signal


class Battery(Node):
    """Authoritative source node. Emits content + user_prompt with confidence=1.0 every iter.

    R7 accumulate mode (cfg['accumulate']=True): appends role=feedback input content
    to emission across iterations, letting seed context evolve.

    state['user_prompt'] injected by engine before bootstrap.
    Ignores all inputs except feedback when accumulate=True.
    """

    def __init__(self, config: dict):
        self.config = config

    def step(self, inputs: dict, state: dict) -> Signal:
        content = self.config["content"] + "\n" + state.get("user_prompt", "")

        if self.config.get("accumulate", False):
            feedback = [
                s for s in inputs.get("feedback", [])
                if s is not Signal.ZERO and s.content
            ]
            if feedback:
                appended = "\n---\n".join(s.content for s in feedback)
                content = content + "\n---\n" + appended
                state["accumulated"] = appended

        return Signal(content=content, confidence=1.0)
