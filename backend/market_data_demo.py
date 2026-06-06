"""
FinAlly — Market Data Live Dashboard
=====================================
A live-updating terminal dashboard that demonstrates the market data layer.
The table stays fixed; only the prices, arrows, tick-delta, session %,
and sparklines refresh in-place on each GBM tick.

Run from the backend/ directory:
    uv run market_data_demo.py

Key concepts demonstrated
--------------------------
create_market_provider()    factory selects Simulator vs Massive API
provider.start(tickers)     seeds the cache, launches the background loop
provider.get_all_prices()   reads a snapshot of the shared PriceCache
provider.add_ticker()       hot-adds a ticker to a running simulation
provider.stop()             cancels the background task cleanly
"""

import asyncio
import os
import sys
import time
from collections import deque

# Make the market package importable when running as a script from backend/.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rich import box
from rich.columns import Columns
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from market import PriceQuote, create_market_provider  # noqa: E402

# ── config ─────────────────────────────────────────────────────────────────────

INITIAL_TICKERS = ["AAPL", "MSFT", "NVDA", "TSLA", "GOOGL"]
N_UPDATES       = 40        # stop automatically after this many ticks
TICK_PAUSE      = 0.55      # slightly longer than the simulator's 0.5 s interval
SPARKLINE_LEN   = 30        # price history length per ticker
ADD_TICKER_AT   = 12        # update number at which AMZN is hot-added

# ── sparkline ──────────────────────────────────────────────────────────────────

_SPARK = "▁▂▃▄▅▆▇█"


def sparkline(prices: list[float]) -> str:
    """Map a price series to a Unicode block-character sparkline."""
    if len(prices) < 2:
        return "·" * len(prices)
    lo, hi = min(prices), max(prices)
    if lo == hi:
        return "─" * len(prices)
    span = hi - lo
    return "".join(_SPARK[int((p - lo) / span * 7)] for p in prices)


# ── renderable builders ────────────────────────────────────────────────────────

def _price_table(
    quotes:  dict[str, PriceQuote],
    prev:    dict[str, float],
    history: dict[str, deque],
    tickers: list[str],
) -> Table:
    tbl = Table(
        box=box.SIMPLE_HEAD,
        header_style="bold bright_white",
        show_edge=False,
        pad_edge=True,
        expand=True,
    )
    tbl.add_column("TICKER",    style="bold",    min_width=7)
    tbl.add_column("PRICE",     justify="right", min_width=11)
    tbl.add_column("",                           width=3)      # arrow
    tbl.add_column("TICK Δ",    justify="right", min_width=8)
    tbl.add_column("SESSION %", justify="right", min_width=10)
    tbl.add_column(f"SPARKLINE  ({SPARKLINE_LEN} ticks)", min_width=SPARKLINE_LEN + 2)

    for ticker in tickers:
        quote = quotes.get(ticker)
        if not quote:
            # Ticker just added — still waiting for its first tick.
            tbl.add_row(
                Text(ticker, style="dim"),
                Text("…",    style="dim"),
                Text("·",    style="dim"),
                Text("—",    style="dim"),
                Text("—",    style="dim"),
                Text("",     style="dim"),
            )
            continue

        prev_price = prev.get(ticker)

        if prev_price is None:
            color, arrow, delta_str = "dim", "·", "—"
        elif quote.price > prev_price:
            color, arrow = "bright_green", "▲"
            delta_str = f"+{quote.price - prev_price:.2f}"
        elif quote.price < prev_price:
            color, arrow = "bright_red", "▼"
            delta_str = f"−{prev_price - quote.price:.2f}"
        else:
            color, arrow, delta_str = "dim", "─", "0.00"

        pct_color = "bright_green" if quote.change_pct >= 0 else "bright_red"
        sign      = "+" if quote.change_pct >= 0 else ""
        spark     = sparkline(list(history[ticker]))

        tbl.add_row(
            Text(ticker,                              style=f"bold {color}"),
            Text(f"${quote.price:,.2f}",              style=color),
            Text(arrow,                               style=f"bold {color}"),
            Text(delta_str,                           style=color),
            Text(f"{sign}{quote.change_pct:.3f}%",    style=pct_color),
            Text(spark,                               style=color),
        )

    return tbl


def _build_layout(
    quotes:       dict[str, PriceQuote],
    prev:         dict[str, float],
    history:      dict[str, deque],
    tickers:      list[str],
    update_num:   int,
    n_updates:    int,
    provider_name: str,
    event_msg:    str,
) -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=5),
        Layout(name="body"),
        Layout(name="footer", size=3),
    )

    # ── header ─────────────────────────────────────────────────────────────────
    ts = time.strftime("%H:%M:%S")
    title = Text(justify="left")
    title.append("FinAlly", style="bold cyan")
    title.append("  │  ", style="dim")
    title.append("Market Data Dashboard", style="bold white")
    title.append("    provider: ", style="dim")
    title.append(provider_name, style="bold yellow")
    title.append(f"    {ts}", style="dim")
    layout["header"].update(Panel(title, padding=(1, 2), border_style="cyan"))

    # ── body ───────────────────────────────────────────────────────────────────
    tbl = _price_table(quotes, prev, history, tickers)
    layout["body"].update(Panel(tbl, border_style="dim", padding=(0, 1)))

    # ── footer ─────────────────────────────────────────────────────────────────
    bar_width  = 36
    filled     = int(update_num / n_updates * bar_width)
    bar        = "█" * filled + "░" * (bar_width - filled)
    footer_txt = Text(justify="left")
    footer_txt.append(f"  update {update_num:>3}/{n_updates}  ", style="dim")
    footer_txt.append(f"[{bar}]", style="cyan")
    if event_msg:
        footer_txt.append(f"  ✦ {event_msg}", style="bold yellow")
    else:
        footer_txt.append("  Ctrl-C to exit early", style="dim")
    layout["footer"].update(Panel(footer_txt, padding=(0, 1), border_style="dim"))

    return layout


# ── main ───────────────────────────────────────────────────────────────────────

async def run_demo() -> None:
    provider = create_market_provider()
    tickers  = list(INITIAL_TICKERS)

    await provider.start(tickers)

    prev:    dict[str, float] = {}
    history: dict[str, deque] = {t: deque(maxlen=SPARKLINE_LEN) for t in tickers}
    event_msg = ""

    try:
        with Live(screen=True, refresh_per_second=4) as live:
            for i in range(1, N_UPDATES + 1):
                await asyncio.sleep(TICK_PAUSE)

                quotes    = provider.get_all_prices()
                event_msg = ""

                # Accumulate price history for sparklines.
                for ticker in tickers:
                    q = quotes.get(ticker)
                    if q:
                        history[ticker].append(q.price)

                # Demo: hot-add AMZN mid-run to show add_ticker().
                if i == ADD_TICKER_AT and "AMZN" not in tickers:
                    provider.add_ticker("AMZN")
                    tickers.append("AMZN")
                    history["AMZN"] = deque(maxlen=SPARKLINE_LEN)
                    event_msg = "add_ticker('AMZN') called — new ticker added live"

                renderable = _build_layout(
                    quotes, prev, history, tickers,
                    update_num=i,
                    n_updates=N_UPDATES,
                    provider_name=type(provider).__name__,
                    event_msg=event_msg,
                )
                live.update(renderable)

                # Snapshot prices for next-tick delta calculation.
                for ticker in tickers:
                    q = quotes.get(ticker)
                    if q:
                        prev[ticker] = q.price

    except KeyboardInterrupt:
        pass
    finally:
        await provider.stop()

    from rich.console import Console
    Console().print("\n[dim]Provider stopped. Demo complete.[/dim]\n")


if __name__ == "__main__":
    asyncio.run(run_demo())
