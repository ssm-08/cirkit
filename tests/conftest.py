import pytest
from cirkit.signal import Signal


@pytest.fixture
def make_signal():
    return lambda content, confidence=0.8: Signal(content=content, confidence=confidence)
