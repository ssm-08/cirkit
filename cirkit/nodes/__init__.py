NODE_REGISTRY: dict = {}

from cirkit.nodes.battery import Battery    # noqa: E402
from cirkit.nodes.sink import Sink          # noqa: E402
from cirkit.nodes.resistor import Resistor  # noqa: E402
from cirkit.nodes.and_gate import AndGate   # noqa: E402
from cirkit.nodes.router import Router      # noqa: E402
from cirkit.nodes.motor import Motor        # noqa: E402

NODE_REGISTRY["battery"] = Battery
NODE_REGISTRY["sink"] = Sink
NODE_REGISTRY["resistor"] = Resistor
NODE_REGISTRY["and_gate"] = AndGate
NODE_REGISTRY["router"] = Router
NODE_REGISTRY["motor"] = Motor
