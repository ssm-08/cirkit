"""Tests for Motor delta-prompt assembly on iter 2+."""
import pytest
from unittest.mock import patch
from cirkit.nodes.motor import Motor
from cirkit import llm


def _llm_result(text="answer. {\"confidence\": 0.8}"):
    return llm.LLMResult(content=text, tokens_in=10, tokens_out=5, cost_usd=0.001)


@pytest.fixture
def motor():
    return Motor({"system": "You are a reviewer."})


def test_first_call_sends_full_prompt(motor, make_signal):
    inputs = {"context": [make_signal("The PR diff")]}
    state = {"session_id": "test-uuid"}
    with patch("cirkit.llm.call_claude", return_value=_llm_result()) as mock:
        motor._call_llm(inputs, state)
    prompt = mock.call_args[0][0]
    assert "[CONTEXT]" in prompt
    assert "You are a reviewer." in prompt
    assert "last_sections" in state


def test_second_call_sends_delta_when_feedback_changes(motor, make_signal):
    inputs_1 = {"context": [make_signal("The PR diff")]}
    state = {"session_id": "test-uuid"}
    with patch("cirkit.llm.call_claude", return_value=_llm_result()):
        motor._call_llm(inputs_1, state)

    inputs_2 = {
        "context": [make_signal("The PR diff")],
        "feedback": [make_signal("Please improve section 2")],
    }
    with patch("cirkit.llm.call_claude", return_value=_llm_result()) as mock:
        motor._call_llm(inputs_2, state)

    prompt = mock.call_args[0][0]
    assert "UPDATE" in prompt
    assert "[UPDATED FEEDBACK]" in prompt
    assert "Please improve section 2" in prompt


def test_second_call_full_prompt_when_all_sections_match(motor, make_signal):
    """If nothing changes (defensive — cache should block), delta returns None → full prompt sent."""
    inputs = {"context": [make_signal("Same content")]}
    state = {"session_id": "test-uuid"}
    with patch("cirkit.llm.call_claude", return_value=_llm_result()):
        motor._call_llm(inputs, state)

    state_copy = dict(state)
    state_copy["last_sections"] = dict(state["last_sections"])  # same sections
    with patch("cirkit.llm.call_claude", return_value=_llm_result()) as mock:
        motor._call_llm(inputs, state_copy)

    prompt = mock.call_args[0][0]
    # delta returns None (nothing changed) → falls back to full prompt
    assert "You are a reviewer." in prompt
    assert "UPDATE" not in prompt


def test_context_change_included_in_delta(motor, make_signal):
    inputs_1 = {"context": [make_signal("Old context")]}
    state = {"session_id": "test-uuid"}
    with patch("cirkit.llm.call_claude", return_value=_llm_result()):
        motor._call_llm(inputs_1, state)

    inputs_2 = {"context": [make_signal("New context")]}
    with patch("cirkit.llm.call_claude", return_value=_llm_result()) as mock:
        motor._call_llm(inputs_2, state)

    prompt = mock.call_args[0][0]
    assert "UPDATE" in prompt
    assert "[UPDATED CONTEXT]" in prompt
    assert "New context" in prompt
