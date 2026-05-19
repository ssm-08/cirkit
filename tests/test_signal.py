import pytest
from dataclasses import FrozenInstanceError
from cirkit.signal import Signal


def test_content_hash_stability():
    s = Signal(content="hello", confidence=0.5)
    assert s.content_hash() == s.content_hash()


def test_content_hash_uniqueness():
    s1 = Signal(content="hello")
    s2 = Signal(content="world")
    assert s1.content_hash() != s2.content_hash()


def test_content_hash_known_value():
    import hashlib
    s = Signal(content="test")
    expected = hashlib.sha1("test".encode("utf-8")).hexdigest()
    assert s.content_hash() == expected


def test_zero_sentinel():
    assert Signal.ZERO.content == ""
    assert Signal.ZERO.confidence == 0.0
    assert Signal.ZERO.contradiction == 0.0
    assert Signal.ZERO.urgency == 0.0
    assert Signal.ZERO.relevance == 0.0
    assert Signal.ZERO.flags == {}


def test_metrics_vector_order():
    s = Signal(content="x", confidence=0.1, contradiction=0.2, urgency=0.3, relevance=0.4)
    assert s.metrics_vector() == (0.1, 0.2, 0.3, 0.4)


def test_metrics_vector_zero():
    assert Signal.ZERO.metrics_vector() == (0.0, 0.0, 0.0, 0.0)


def test_flags_excluded_from_equality():
    s1 = Signal(content="x", confidence=0.5)
    s2 = Signal(content="x", confidence=0.5, flags={"a": True})
    assert s1 == s2


def test_flags_default_empty():
    s = Signal(content="y")
    assert s.flags == {}


def test_frozen_raises_on_set():
    s = Signal(content="z", confidence=0.5)
    with pytest.raises(FrozenInstanceError):
        s.confidence = 0.9
