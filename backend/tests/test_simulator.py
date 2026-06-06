import asyncio
import pytest
from market.simulator import MarketSimulator, _TickerState, SEED_PRICES


def test_seed_price_is_initial_price():
    state = _TickerState.from_seed("AAPL")
    assert state.price == SEED_PRICES["AAPL"]
    assert state.prev_close == SEED_PRICES["AAPL"]


def test_gbm_price_bounded_after_many_ticks():
    import random
    rng = random.Random(0)
    state = _TickerState.from_seed("TSLA")  # high vol ticker
    for _ in range(10_000):
        state.tick(0.0, rng)
    assert 0.01 < state.price < 50_000


def test_unknown_ticker_uses_default_seed():
    state = _TickerState.from_seed("ZZZZZ")
    assert state.price == 100.00


@pytest.mark.asyncio
async def test_add_ticker_appears_in_cache_immediately():
    sim = MarketSimulator(seed=1)
    await sim.start(["AAPL"])
    sim.add_ticker("PYPL")
    quote = sim.get_price("PYPL")
    assert quote is not None
    assert quote.price == 100.00
    await sim.stop()


@pytest.mark.asyncio
async def test_remove_ticker_disappears_from_cache():
    sim = MarketSimulator(seed=2)
    await sim.start(["AAPL", "MSFT"])
    sim.remove_ticker("MSFT")
    assert sim.get_price("MSFT") is None
    await sim.stop()


@pytest.mark.asyncio
async def test_prices_change_after_two_ticks():
    sim = MarketSimulator(seed=7)
    await sim.start(["AAPL"])
    initial = sim.get_price("AAPL").price
    await asyncio.sleep(1.1)   # wait for ≥2 ticks
    updated = sim.get_price("AAPL").price
    assert updated != initial
    await sim.stop()


@pytest.mark.asyncio
async def test_deterministic_with_same_seed():
    async def run_sim(seed):
        sim = MarketSimulator(seed=seed)
        await sim.start(["AAPL"])
        await asyncio.sleep(1.1)
        price = sim.get_price("AAPL").price
        await sim.stop()
        return price

    p1 = await run_sim(42)
    p2 = await run_sim(42)
    assert p1 == p2


@pytest.mark.asyncio
async def test_all_prices_returns_all_started_tickers():
    sim = MarketSimulator(seed=3)
    await sim.start(["AAPL", "MSFT", "GOOGL"])
    prices = sim.get_all_prices()
    assert set(prices.keys()) == {"AAPL", "MSFT", "GOOGL"}
    await sim.stop()


def test_add_existing_ticker_is_noop():
    """Adding a ticker that already exists should not reset its price."""
    import asyncio
    sim = MarketSimulator(seed=5)
    asyncio.run(sim.start(["AAPL"]))
    # Manually set price to verify it's not reset
    sim._states["AAPL"].price = 999.0
    sim.add_ticker("AAPL")  # should be no-op
    assert sim._states["AAPL"].price == 999.0
    asyncio.run(sim.stop())


def test_price_floor_prevents_zero():
    import random
    rng = random.Random(99)
    state = _TickerState.from_seed("AAPL")
    state.price = 0.001  # near zero
    for _ in range(100):
        state.tick(-10.0, rng)  # extreme negative shock
    assert state.price >= 0.01
