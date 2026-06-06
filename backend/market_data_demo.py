"""
FinAlly — Market Data Demo
==========================
Demonstrates the market data layer: factory, simulator, price cache, and
the MarketDataProvider interface.

Run from the backend/ directory:
    uv run market_data_demo.py

What you will see
-----------------
* The MarketSimulator starts up and seeds 5 tickers at realistic prices.
* Every 500 ms (one GBM tick) the table refreshes with live prices.
* Green rows = price moved up since last tick.
* Red rows  = price moved down since last tick.
* "Session %" tracks drift from the opening seed price (prev_close).

Key concepts shown
------------------
* create_market_provider()  — factory picks Simulator vs Massive API
* provider.start(tickers)   — begins the background async task
* provider.get_all_prices() — reads the shared PriceCache snapshot
* provider.add_ticker()     — hot-adds a ticker at runtime
* provider.stop()           — clean shutdown, cancels the background task
"""

import asyncio
import os
import sys
import time

# Allow running as a plain script from the backend/ directory.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from market import create_market_provider, PriceQuote  # noqa: E402

# ── demo config ────────────────────────────────────────────────────────────────

TICKERS       = ["AAPL", "MSFT", "NVDA", "TSLA", "GOOGL"]
N_UPDATES     = 10   # how many 500 ms ticks to display
TICK_PAUSE    = 0.55 # slightly longer than the simulator's 0.5 s tick interval

# ── ANSI helpers ───────────────────────────────────────────────────────────────

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"


def _row(quote: PriceQuote, prev_price: float | None) -> str:
    """Format one table row with colour based on tick direction."""
    if prev_price is None:
        color, arrow = DIM, "·"
    elif quote.price > prev_price:
        color, arrow = GREEN, "▲"
    elif quote.price < prev_price:
        color, arrow = RED,   "▼"
    else:
        color, arrow = DIM,   "="

    sign = "+" if quote.change_pct >= 0 else ""
    tick_delta = "" if prev_price is None else f"{quote.price - prev_price:+.2f}"

    return (
        f"  {color}{BOLD}{quote.ticker:<6}{RESET}"
        f"  {color}${quote.price:>9.2f}{RESET}"
        f"  {color}{arrow}{RESET}"
        f"  {color}{tick_delta:>7}{RESET}"
        f"  {color}{sign}{quote.change_pct:.3f}%{RESET}"
    )


def _header() -> str:
    return (
        f"  {DIM}{'TICKER':<6}  {'PRICE':>10}     {'TICK Δ':>7}  SESSION %{RESET}"
    )


def _divider() -> str:
    return f"  {DIM}{'─' * 50}{RESET}"


# ── main demo ──────────────────────────────────────────────────────────────────

async def run_demo() -> None:
    # 1. Factory: returns MarketSimulator when MASSIVE_API_KEY is not set.
    provider = create_market_provider()

    print(f"\n{BOLD}  FinAlly — Market Data Demo{RESET}")
    print(_divider())
    print(f"  Provider  : {BOLD}{type(provider).__name__}{RESET}")
    print(f"  Tickers   : {', '.join(TICKERS)}")
    print(f"  Updates   : {N_UPDATES} × {TICK_PAUSE:.2f} s")
    print(_divider())
    print()

    # 2. Start: seeds each ticker in the cache and launches the background loop.
    await provider.start(TICKERS)

    prev: dict[str, float] = {}

    try:
        for i in range(1, N_UPDATES + 1):
            await asyncio.sleep(TICK_PAUSE)

            # 3. Read: get_all_prices() returns a snapshot of the shared cache.
            prices = provider.get_all_prices()

            ts = time.strftime("%H:%M:%S")
            print(f"  {DIM}update {i:>2}/{N_UPDATES}  {ts}{RESET}")
            print(_header())
            print(_divider())

            for ticker in TICKERS:
                quote = prices.get(ticker)
                if quote:
                    print(_row(quote, prev.get(ticker)))
                    prev[ticker] = quote.price

            # On update 5, hot-add a new ticker to show dynamic addition.
            if i == 5:
                new_ticker = "AMZN"
                provider.add_ticker(new_ticker)
                TICKERS.append(new_ticker)
                print(
                    f"\n  {YELLOW}→ add_ticker('{new_ticker}') called — "
                    f"appears in next tick{RESET}"
                )

            print()

    finally:
        # 4. Stop: cancels the asyncio background task cleanly.
        await provider.stop()

    print(_divider())
    print(f"  {DIM}Provider stopped. Demo complete.{RESET}\n")


if __name__ == "__main__":
    asyncio.run(run_demo())
