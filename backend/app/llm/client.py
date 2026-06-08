"""LiteLLM client: calls OpenRouter/Cerebras or returns a mock response."""

from __future__ import annotations

import logging
import os

from litellm import completion

from .models import LLMResponse

logger = logging.getLogger(__name__)

MODEL = "openrouter/openai/gpt-oss-120b"
EXTRA_BODY = {"provider": {"order": ["cerebras"]}}

MOCK_MESSAGE = (
    "I'm FinAlly, your AI trading assistant. I can analyze your portfolio, "
    "suggest trades, and execute them on your behalf. How can I help you today?"
)


def call_llm(system_prompt: str, history: list[dict], user_message: str) -> LLMResponse:
    """Call the LLM and return a structured response.

    Uses LLM_MOCK=true for deterministic test responses without an API call.
    """
    if os.environ.get("LLM_MOCK", "").lower() == "true":
        logger.debug("LLM_MOCK=true — returning mock response")
        return LLMResponse(message=MOCK_MESSAGE, trades=[], watchlist_changes=[])

    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_message})

    logger.debug("Calling LLM with %d messages", len(messages))
    response = completion(
        model=MODEL,
        messages=messages,
        response_format=LLMResponse,
        reasoning_effort="low",
        extra_body=EXTRA_BODY,
    )
    content = response.choices[0].message.content
    return LLMResponse.model_validate_json(content)
