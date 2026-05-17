import pytest
from unittest.mock import patch
from cirkit.graph import load_circuit
from cirkit.engine import run
from cirkit.confidence import parse_confidence

MOCK_RESPONSE = "This is a mock code review.\n{\"confidence\":0.8}"


def test_mock_motor_converges():
    with patch("cirkit.llm.call_claude", return_value=MOCK_RESPONSE):
        circuit = load_circuit("examples/pr_review.json")
        result = run(circuit, "Refactored auth.py to use bcrypt instead of MD5.")
        assert result.converged is True
        assert result.iterations <= 6
        assert result.output.content != ""


def test_delta_history_nondecreasing_after_iter2():
    with patch("cirkit.llm.call_claude", return_value=MOCK_RESPONSE):
        circuit = load_circuit("examples/pr_review.json")
        result = run(circuit, "test prompt")
        if len(result.delta_history) > 2:
            later_deltas = result.delta_history[2:]
            for i in range(len(later_deltas) - 1):
                assert later_deltas[i] >= later_deltas[i + 1] - 0.001


def test_confidence_fallback_range():
    content, conf = parse_confidence("Some content without json")
    assert 0.1 <= conf <= 0.9


def test_confidence_json_parsed():
    content, conf = parse_confidence('Answer.\n{"confidence": 0.85}')
    assert content == "Answer."
    assert conf == 0.85


def test_confidence_hedge_cap():
    # I5: hedge phrases do NOT cap explicit JSON confidence — only the fallback path is capped
    content, conf = parse_confidence('Actually I was wrong.\n{"confidence": 0.9}')
    assert conf == pytest.approx(0.9), (
        "Explicit JSON confidence must not be capped by hedge phrases (I5)"
    )


def test_confidence_empty_string():
    content, conf = parse_confidence("")
    assert content == ""
    assert conf == 0.1
