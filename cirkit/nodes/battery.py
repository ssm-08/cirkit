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
        if "content" not in config:
            raise ValueError("Battery config requires 'content'")
        self.config = config

    def step(self, inputs: dict, state: dict) -> Signal:
        user_prompt = state.get("user_prompt", "")
        content = self.config["content"] + ("\n" + user_prompt if user_prompt else "")

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
