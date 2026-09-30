from app.incidents import STATE
from app.mock_llm import FakeLLM


def test_fake_llm_output_and_usage_are_deterministic(monkeypatch) -> None:
    monkeypatch.setitem(STATE, "cost_spike", False)
    llm = FakeLLM()

    first = llm.generate("Feature=qa\nQuestion=same input")
    second = llm.generate("Feature=qa\nQuestion=same input")

    assert first.text == second.text
    assert first.usage.input_tokens == second.usage.input_tokens
    assert first.usage.output_tokens == second.usage.output_tokens
