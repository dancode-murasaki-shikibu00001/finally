import threading
from market.cache import PriceCache
from market.base import PriceQuote


def _quote(ticker: str, price: float) -> PriceQuote:
    return PriceQuote(ticker=ticker, price=price, prev_close=price,
                      change_pct=0.0, volume=0.0, timestamp_ms=0)


def test_update_and_get():
    cache = PriceCache()
    cache.update(_quote("AAPL", 190.0))
    q = cache.get("AAPL")
    assert q is not None and q.price == 190.0


def test_get_missing_returns_none():
    cache = PriceCache()
    assert cache.get("ZZZZ") is None


def test_get_all_returns_copy():
    cache = PriceCache()
    cache.update(_quote("AAPL", 190.0))
    snapshot = cache.get_all()
    snapshot["AAPL"] = None   # mutate the copy
    assert cache.get("AAPL").price == 190.0  # original unaffected


def test_remove():
    cache = PriceCache()
    cache.update(_quote("AAPL", 190.0))
    cache.remove("AAPL")
    assert cache.get("AAPL") is None


def test_tickers():
    cache = PriceCache()
    cache.update(_quote("AAPL", 190.0))
    cache.update(_quote("MSFT", 415.0))
    assert set(cache.tickers()) == {"AAPL", "MSFT"}


def test_thread_safety():
    cache = PriceCache()
    errors = []

    def writer():
        try:
            for i in range(1000):
                cache.update(_quote("AAPL", float(i)))
        except Exception as e:
            errors.append(e)

    def reader():
        try:
            for _ in range(1000):
                cache.get_all()
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=writer), threading.Thread(target=reader)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
