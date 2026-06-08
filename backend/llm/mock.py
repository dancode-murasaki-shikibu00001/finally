from .schemas import ChatResponse


def get_mock_response() -> ChatResponse:
    return ChatResponse(
        message="I'm FinAlly, your AI trading assistant. I can analyze your portfolio and execute trades on your behalf. How can I help you today?",
        trades=[],
        watchlist_changes=[],
    )
