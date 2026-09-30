from __future__ import annotations

import time
from dataclasses import dataclass

from .incidents import STATE
from .tracing import get_langfuse_client, observe


@dataclass
class FakeUsage:
    input_tokens: int
    output_tokens: int


@dataclass
class FakeResponse:
    text: str
    usage: FakeUsage
    model: str
    ttft_ms: int


class FakeLLM:
    def __init__(self, model: str = "claude-sonnet-4-5") -> None:
        self.model = model

    @observe(name="generation", as_type="generation", capture_input=False, capture_output=False)
    def generate(self, prompt_text: str, *, prompt: object | None = None) -> FakeResponse:
        started = time.perf_counter()
        time.sleep(0.05)  # mô phỏng thời điểm token đầu tiên sẵn sàng
        ttft_ms = int((time.perf_counter() - started) * 1000)
        time.sleep(0.10)
        input_tokens = max(20, len(prompt_text) // 4)
        answer = (
            "Starter answer. You should improve this output logic and add better quality checks. "
            "Use retrieved context and keep responses concise."
        )
        output_tokens = max(1, len(answer) // 4)
        if STATE["cost_spike"]:
            output_tokens *= 4
        response = FakeResponse(
            text=answer,
            usage=FakeUsage(input_tokens, output_tokens),
            model=self.model,
            ttft_ms=ttft_ms,
        )
        input_cost = (input_tokens / 1_000_000) * 3
        output_cost = (output_tokens / 1_000_000) * 15
        get_langfuse_client().update_current_generation(
            model=self.model,
            usage_details={"input": input_tokens, "output": output_tokens},
            cost_details={
                "input": input_cost,
                "output": output_cost,
                "total": round(input_cost + output_cost, 6),
            },
            prompt=prompt,
        )
        return response
