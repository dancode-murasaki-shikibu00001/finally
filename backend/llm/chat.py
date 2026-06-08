import os
import json
from litellm import completion
from .schemas import ChatResponse, TradeRequest, WatchlistChange
from .mock import get_mock_response

MODEL = "openrouter/openai/gpt-oss-120b"
EXTRA_BODY = {"provider": {"order": ["cerebras"]}}

SYSTEM_PROMPT = """You are FinAlly, an AI trading assistant for a simulated trading workstation.
You help users analyze their portfolio, suggest trades, and execute them on their behalf.
Be concise, data-driven, and professional.
You can execute trades and manage the watchlist by including them in your structured response.
Always respond with valid JSON matching the required schema.
This is a simulated environment with fake money — you can be bold with suggestions."""


def process_chat_message(
    user_id: str,
    user_message: str,
    portfolio_context: dict,
    chat_history: list[dict],
) -> ChatResponse:
    if os.getenv("LLM_MOCK", "false").lower() == "true":
        return get_mock_response()

    # Build messages list
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Add portfolio context as system context
    portfolio_summary = json.dumps(portfolio_context, indent=2)
    messages.append({
        "role": "system",
        "content": f"Current portfolio context:\n{portfolio_summary}",
    })

    # Add recent chat history (last 20 messages)
    for msg in chat_history[-20:]:
        messages.append({"role": msg["role"], "content": msg["content"]})

    # Add the new user message
    messages.append({"role": "user", "content": user_message})

    try:
        response = completion(
            model=MODEL,
            messages=messages,
            response_format=ChatResponse,
            reasoning_effort="low",
            extra_body=EXTRA_BODY,
            api_key=os.getenv("OPENROUTER_API_KEY"),
            api_base="https://openrouter.ai/api/v1",
            extra_headers={
                "X-Title": "FinAlly Trading Assistant",
                "HTTP-Referer": "https://finally.app",
            },
        )

        content = response.choices[0].message.content
        if isinstance(content, str):
            return ChatResponse.model_validate_json(content)
        return ChatResponse.model_validate(content)

    except Exception as e:
        return ChatResponse(
            message=f"I encountered an error processing your request: {str(e)}. Please try again.",
            trades=[],
            watchlist_changes=[],
        )
