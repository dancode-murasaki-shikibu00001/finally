import asyncio
from unittest.mock import patch, MagicMock
from market.massive_client import MassiveClient
from market.base import PriceQuote

MOCK_RESPONSE = {
    "status": "OK",
    "results": [
        {
            "ticker": "AAPL",
            "session": {
                "close": 191.00,
                "previous_close": 189.50,
                "change_percent": 0.79,
                "volume": 52_000_000,
            },
            "last_trade": {
                "price": 191.34,
                "sip_timestamp": 1_700_000_000_000,
            },
            "updated": 1_700_000_000_000,
        }
    ],
}


def test_parse_snapshot_response():
    client = MassiveClient(api_key="test")
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_RESPONSE
        mock_resp.raise_for_status = lambda: None
        mock_get.return_value = mock_resp

        quotes = client._fetch_chunk(["AAPL"])

    assert len(quotes) == 1
    q = quotes[0]
    assert q.ticker == "AAPL"
    assert q.price == 191.34
    assert q.prev_close == 189.50
    assert q.change_pct == 0.79
    assert q.volume == 52_000_000
    assert q.timestamp_ms == 1_700_000_000_000


def test_missing_last_trade_falls_back_to_session_close():
    response = {
        "status": "OK",
        "results": [
            {
                "ticker": "AAPL",
                "session": {"close": 190.00, "previous_close": 189.00},
                "last_trade": {},
                "updated": 1_000,
            }
        ],
    }
    client = MassiveClient(api_key="test")
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = response
        mock_resp.raise_for_status = lambda: None
        mock_get.return_value = mock_resp

        quotes = client._fetch_chunk(["AAPL"])

    assert quotes[0].price == 190.00


def test_http_error_does_not_crash_poll():
    client = MassiveClient(api_key="test")
    client._tickers = {"AAPL"}

    with patch.object(client, "_fetch_snapshots", side_effect=Exception("network down")):
        asyncio.run(client._poll_once())   # must not raise

    # cache remains empty — no crash
    assert client.get_all_prices() == {}


def test_add_ticker_included_in_next_poll():
    client = MassiveClient(api_key="test")
    client._tickers = {"AAPL"}
    client.add_ticker("MSFT")
    assert "MSFT" in client._tickers


def test_remove_ticker_excluded_from_polling():
    client = MassiveClient(api_key="test")
    client._tickers = {"AAPL", "MSFT"}
    client.remove_ticker("MSFT")
    assert "MSFT" not in client._tickers
    assert client.get_price("MSFT") is None


def test_rate_limit_retry():
    """429 response triggers backoff and retry."""
    client = MassiveClient(api_key="test")

    call_count = 0

    def mock_get(url, params, timeout):
        nonlocal call_count
        call_count += 1
        mock_resp = MagicMock()
        if call_count < 2:
            mock_resp.status_code = 429
        else:
            mock_resp.status_code = 200
            mock_resp.json.return_value = MOCK_RESPONSE
            mock_resp.raise_for_status = lambda: None
        return mock_resp

    with patch("requests.get", side_effect=mock_get), \
         patch("time.sleep"):  # don't actually sleep in tests
        result = client._get_with_retry(
            "https://api.massive.com/v3/snapshot",
            params={"apiKey": "test"},
        )

    assert result == MOCK_RESPONSE
    assert call_count == 2


def test_change_pct_computed_when_missing():
    """When change_percent is absent, it's computed from price and prev_close."""
    response = {
        "status": "OK",
        "results": [
            {
                "ticker": "TSLA",
                "session": {"close": 250.00, "previous_close": 200.00},
                "last_trade": {"price": 250.00},
                "updated": 1_000,
            }
        ],
    }
    client = MassiveClient(api_key="test")
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = response
        mock_resp.raise_for_status = lambda: None
        mock_get.return_value = mock_resp

        quotes = client._fetch_chunk(["TSLA"])

    # (250 - 200) / 200 * 100 = 25.0
    assert quotes[0].change_pct == 25.0
