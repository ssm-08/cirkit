from __future__ import annotations
import hashlib
from dataclasses import dataclass, field
from typing import ClassVar


@dataclass(frozen=True)
class Signal:
    """Immutable signal propagated between nodes. See plan R4 for flags field."""
    content: str
    confidence: float = 0.0
    contradiction: float = 0.0
    urgency: float = 0.0
    relevance: float = 0.0
    # compare=False, hash=False: flags do NOT affect Signal equality or hashing.
    # Two Signals with same content/metrics but different flags ARE considered equal.
    # Flags are engine-control metadata (e.g. consensus_locked), not content.
    flags: dict = field(default_factory=dict, compare=False, hash=False)

    ZERO: ClassVar["Signal"]  # sentinel — assigned after class def

    def content_hash(self) -> str:
        return hashlib.sha1(self.content.encode("utf-8")).hexdigest()

    def metrics_vector(self) -> tuple[float, float, float, float]:
        return (self.confidence, self.contradiction, self.urgency, self.relevance)


Signal.ZERO = Signal(content="", confidence=0.0, contradiction=0.0, urgency=0.0, relevance=0.0)
