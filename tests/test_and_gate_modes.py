"""R5: AND-Gate merge modes and early-exit threshold."""
import pytest
from cirkit.signal import Signal
from cirkit.nodes.and_gate import AndGate


def make_gate(merge_mode="concat", threshold=0.5, early_exit_threshold=0.9):
    return AndGate({
        "threshold": threshold,
        "merge_mode": merge_mode,
        "early_exit_threshold": early_exit_threshold,
    })


def test_concat_mode():
    g = make_gate("concat")
    s1 = Signal(content="alpha", confidence=0.8)
    s2 = Signal(content="beta", confidence=0.9)
    out = g.step({"context": [s1], "peer": [s2]}, {})
    assert out.content == "alpha\n---\nbeta"


def test_dedupe_removes_duplicate_lines():
    g = make_gate("dedupe")
    s1 = Signal(content="line one\nshared line", confidence=0.8)
    s2 = Signal(content="shared line\nline two", confidence=0.8)
    out = g.step({"context": [s1], "peer": [s2]}, {})
    lines = out.content.splitlines()
    assert lines.count("shared line") == 1
    assert "line one" in out.content
    assert "line two" in out.content


def test_dedupe_case_insensitive():
    g = make_gate("dedupe")
    s1 = Signal(content="Hello World", confidence=0.8)
    s2 = Signal(content="hello world", confidence=0.8)
    out = g.step({"context": [s1], "peer": [s2]}, {})
    lower_count = out.content.lower().count("hello world")
    assert lower_count == 1


def test_dedupe_preserves_first_occurrence_order():
    g = make_gate("dedupe")
    s1 = Signal(content="first\nsecond", confidence=0.8)
    s2 = Signal(content="second\nthird", confidence=0.8)
    out = g.step({"context": [s1], "peer": [s2]}, {})
    lines = out.content.splitlines()
    assert lines[0] == "first"
    assert "second" in lines
    assert "third" in lines


def test_early_exit_sets_consensus_locked():
    g = make_gate("concat", threshold=0.5, early_exit_threshold=0.7)
    s1 = Signal(content="a", confidence=0.85)
    s2 = Signal(content="b", confidence=0.9)
    out = g.step({"context": [s1], "peer": [s2]}, {})
    assert out.flags.get("consensus_locked") is True


def test_early_exit_not_set_below_threshold():
    g = make_gate("concat", threshold=0.5, early_exit_threshold=0.9)
    s1 = Signal(content="a", confidence=0.8)
    s2 = Signal(content="b", confidence=0.75)
    out = g.step({"context": [s1], "peer": [s2]}, {})
    assert "consensus_locked" not in out.flags


def test_m3_non_standard_roles_deterministic_regardless_of_dict_order():
    """M3: Merge content must be identical regardless of non-standard role insertion order."""
    from cirkit.nodes.and_gate import AndGate
    from cirkit.signal import Signal

    gate = AndGate({"threshold": 0.5, "early_exit_threshold": 0.99, "merge_mode": "concat"})
    s_apple = Signal(content="apple", confidence=0.8)
    s_zebra = Signal(content="zebra", confidence=0.8)

    out1 = gate.step({"z_role": [s_zebra], "a_role": [s_apple]}, {})
    out2 = gate.step({"a_role": [s_apple], "z_role": [s_zebra]}, {})
    assert out1.content == out2.content, (
        f"Merge content differs by dict insertion order:\n{out1.content!r}\nvs\n{out2.content!r}"
    )


def test_metrics_are_min_of_inputs():
    g = make_gate("concat", threshold=0.5)
    s1 = Signal(content="a", confidence=0.8, contradiction=0.2, urgency=0.6, relevance=0.9)
    s2 = Signal(content="b", confidence=0.6, contradiction=0.1, urgency=0.4, relevance=0.7)
    out = g.step({"context": [s1], "peer": [s2]}, {})
    assert out.confidence == 0.6
    assert out.contradiction == 0.1
    assert out.urgency == 0.4
    assert out.relevance == 0.7
