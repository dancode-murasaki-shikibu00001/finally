import os
from .base import MarketDataProvider
from .simulator import MarketSimulator
from .massive_client import MassiveClient

_provider: MarketDataProvider | None = None


def create_market_provider() -> MarketDataProvider:
    """
    Read MASSIVE_API_KEY from the environment.
    Return MassiveClient if set and non-empty, else MarketSimulator.
    """
    api_key = os.getenv("MASSIVE_API_KEY", "").strip()
    if api_key:
        poll_interval = float(os.getenv("MASSIVE_POLL_INTERVAL", "15.0"))
        return MassiveClient(api_key=api_key, poll_interval=poll_interval)
    return MarketSimulator()


def get_provider() -> MarketDataProvider:
    """Return the initialized provider. Raises if called before startup."""
    if _provider is None:
        raise RuntimeError("Market provider not initialized — call init_provider() first")
    return _provider


def init_provider(provider: MarketDataProvider) -> None:
    """Store the provider singleton. Called once during FastAPI lifespan."""
    global _provider
    _provider = provider
