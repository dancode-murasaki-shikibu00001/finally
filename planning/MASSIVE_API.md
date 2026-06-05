# Massive API Reference (formerly Polygon.io)

Massive (rebranded from Polygon.io on 2025-10-30) provides REST and WebSocket APIs for US equity market data. All existing Polygon.io API keys and integrations remain fully functional; only the base URL changes.

- **New base URL**: `https://api.massive.com`
- **Legacy base URL**: `https://api.polygon.io` (still works)
- **Python package**: `massive` (pip install -U massive) — same package, renamed from `polygon-api-client`

---

## Authentication

Every request requires an API key. Two methods are supported:

**Query parameter (simplest):**
```
GET https://api.massive.com/v2/snapshot/locale/us/markets/stocks/tickers/AAPL?apiKey=YOUR_KEY
```

**Authorization header (preferred for production):**
```
Authorization: Bearer YOUR_KEY
```

---

## Rate Limits by Tier

| Tier        | REST Requests  | Data Latency     | WebSocket |
|-------------|---------------|------------------|-----------|
| Free        | 5 / minute    | Delayed (varies) | No        |
| Starter     | Limited       | 15-min delay     | Yes       |
| Developer   | Limited       | 15-min delay     | Yes       |
| Advanced    | Unlimited     | Real-time        | Yes       |
| Business    | Unlimited     | Real-time + FMV  | Yes       |

For FinAlly the practical tiers are **Starter/Developer** (15-second polling cadence is fine) or **Free** (15-second polling with 15-minute delay — good for dev/testing only).

---

## Snapshot Endpoints (Current Prices)

### Single Ticker Snapshot

```
GET /v2/snapshot/locale/us/markets/stocks/tickers/{ticker}
```

Returns the most recent trade, quote, and daily aggregate for one ticker.

**Response schema (abridged):**
```json
{
  "status": "OK",
  "ticker": {
    "ticker": "AAPL",
    "day": {
      "o": 189.50,
      "h": 191.25,
      "l": 188.90,
      "c": 190.42,
      "v": 52000000
    },
    "prevDay": {
      "c": 189.50
    },
    "lastTrade": {
      "price": 190.42,
      "size": 100,
      "sip_timestamp": 1700000000000
    },
    "lastQuote": {
      "ask_price": 190.43,
      "bid_price": 190.41
    },
    "todaysChange": 0.92,
    "todaysChangePerc": 0.49,
    "updated": 1700000000000
  }
}
```

Key fields:
- `ticker.day.c` — current session close (last price during market hours)
- `ticker.lastTrade.price` — last trade price (most accurate current price)
- `ticker.todaysChangePerc` — % change from previous close
- `ticker.updated` — millisecond timestamp of last update

---

### Unified Snapshot — Multiple Tickers (preferred for FinAlly)

```
GET /v3/snapshot?ticker.any_of=AAPL,MSFT,GOOGL&limit=250
```

Fetches up to 250 tickers in a single request. This is the primary endpoint to use in FinAlly for polling the watchlist.

**Query parameters:**
| Parameter        | Type    | Description                                      |
|-----------------|---------|--------------------------------------------------|
| `ticker.any_of` | string  | Comma-separated tickers (max 250)                |
| `limit`         | integer | Results per page (max 250, default 10)           |
| `order`         | string  | `asc` or `desc` sort                             |

**Response schema:**
```json
{
  "status": "OK",
  "results": [
    {
      "ticker": "AAPL",
      "name": "Apple Inc.",
      "session": {
        "open": 189.50,
        "high": 191.25,
        "low": 188.90,
        "close": 190.42,
        "volume": 52000000,
        "change": 0.92,
        "change_percent": 0.49,
        "previous_close": 189.50
      },
      "last_trade": {
        "price": 190.42,
        "size": 100,
        "sip_timestamp": 1700000000000
      },
      "last_quote": {
        "ask_price": 190.43,
        "bid_price": 190.41
      },
      "market_status": "open",
      "updated": 1700000000000
    }
  ]
}
```

Key fields:
- `results[n].session.close` — current price during market hours
- `results[n].last_trade.price` — last trade price (most up-to-date)
- `results[n].session.change_percent` — % change from previous close
- `results[n].session.previous_close` — previous session close (source of daily % change)

---

### Full Market Snapshot (all tickers)

```
GET /v2/snapshot/locale/us/markets/stocks/tickers?tickers=AAPL,TSLA,GOOG
```

Same as the unified snapshot but using the v2 API. For FinAlly use the v3 unified snapshot instead — it has cleaner field names.

---

## End-of-Day (EOD) Endpoints

### Daily Open/Close for One Date

```
GET /v1/open-close/{ticker}/{date}?adjusted=true
```

Example: `GET /v1/open-close/AAPL/2024-01-15?adjusted=true`

**Response:**
```json
{
  "symbol": "AAPL",
  "from": "2024-01-15",
  "open": 185.00,
  "high": 186.75,
  "low": 184.20,
  "close": 186.40,
  "volume": 58000000,
  "preMarket": 184.90,
  "afterHours": 186.60,
  "status": "OK"
}
```

### Historical Aggregates (OHLCV bars)

```
GET /v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from}/{to}
```

Example — daily bars for January 2024:
```
GET /v2/aggs/ticker/AAPL/range/1/day/2024-01-01/2024-01-31?limit=50000
```

Supported `timespan` values: `second`, `minute`, `hour`, `day`, `week`, `month`, `quarter`, `year`

**Response:**
```json
{
  "status": "OK",
  "results": [
    {
      "t": 1704067200000,
      "o": 185.00,
      "h": 186.75,
      "l": 184.20,
      "c": 186.40,
      "v": 58000000,
      "vw": 185.85,
      "n": 420000
    }
  ]
}
```

Fields: `t` = timestamp (ms), `o/h/l/c` = OHLC, `v` = volume, `vw` = VWAP, `n` = trade count.

---

## WebSocket API

For FinAlly we use REST polling — WebSocket is documented here for reference only.

**Connection URL:** `wss://socket.massive.com`

Subscription topic format: `{channel}.{ticker}` or `{channel}.*` for all tickers.

| Channel | Data                        |
|---------|-----------------------------|
| `T`     | Individual trades           |
| `Q`     | NBBO quotes                 |
| `AM`    | 1-minute aggregate bars     |
| `AS`    | 1-second aggregate bars     |

**Auth + subscribe sequence:**
```python
import asyncio, json, websockets

async def stream():
    async with websockets.connect("wss://socket.massive.com") as ws:
        await ws.send(json.dumps({"action": "auth", "params": "YOUR_KEY"}))
        await ws.send(json.dumps({"action": "subscribe", "params": "AM.AAPL,AM.MSFT"}))
        async for msg in ws:
            print(json.loads(msg))

asyncio.run(stream())
```

---

## Python Code Examples

### Install

```bash
pip install -U massive
# or for requests-only usage:
pip install requests
```

### Using the Official SDK

```python
from massive import RESTClient

client = RESTClient(api_key="YOUR_KEY")

# Single ticker snapshot
snap = client.get_snapshot(ticker="AAPL")
print(snap)

# Previous close
prev = client.get_previous_close(ticker="AAPL")
print(prev)

# Daily aggregates (auto-paginated iterator)
for bar in client.list_aggs("AAPL", 1, "day", "2024-01-01", "2024-01-31"):
    print(bar.timestamp, bar.close)

# Minute aggregates
for bar in client.list_aggs("AAPL", 1, "minute", "2024-01-15", "2024-01-15", limit=50000):
    print(bar)
```

### Using `requests` (no SDK dependency)

```python
import requests

BASE = "https://api.massive.com"
API_KEY = "YOUR_KEY"

def fetch_snapshots(tickers: list[str]) -> list[dict]:
    """Fetch latest prices for a list of tickers in one request."""
    resp = requests.get(
        f"{BASE}/v3/snapshot",
        params={
            "apiKey": API_KEY,
            "ticker.any_of": ",".join(tickers),
            "limit": 250,
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()

    results = []
    for r in data.get("results", []):
        session = r.get("session", {})
        last_trade = r.get("last_trade", {})
        results.append({
            "ticker": r["ticker"],
            # Prefer last_trade.price; fall back to session.close
            "price": last_trade.get("price") or session.get("close"),
            "prev_close": session.get("previous_close"),
            "change_pct": session.get("change_percent"),
            "volume": session.get("volume"),
            "updated_ms": r.get("updated"),
        })
    return results


def fetch_eod(ticker: str, date: str) -> dict:
    """Fetch end-of-day OHLCV for ticker on date (YYYY-MM-DD)."""
    resp = requests.get(
        f"{BASE}/v1/open-close/{ticker}/{date}",
        params={"apiKey": API_KEY, "adjusted": "true"},
        timeout=10,
    )
    resp.raise_for_status()
    d = resp.json()
    return {
        "ticker": d["symbol"],
        "date": d["from"],
        "open": d["open"],
        "high": d["high"],
        "low": d["low"],
        "close": d["close"],
        "volume": d["volume"],
        "pre_market": d.get("preMarket"),
        "after_hours": d.get("afterHours"),
    }


def fetch_daily_bars(ticker: str, from_date: str, to_date: str) -> list[dict]:
    """Fetch daily OHLCV bars for a date range."""
    resp = requests.get(
        f"{BASE}/v2/aggs/ticker/{ticker}/range/1/day/{from_date}/{to_date}",
        params={"apiKey": API_KEY, "limit": 50000, "adjusted": "true"},
        timeout=10,
    )
    resp.raise_for_status()
    return [
        {
            "timestamp_ms": bar["t"],
            "open": bar["o"],
            "high": bar["h"],
            "low": bar["l"],
            "close": bar["c"],
            "volume": bar["v"],
            "vwap": bar.get("vw"),
        }
        for bar in resp.json().get("results", [])
    ]


if __name__ == "__main__":
    print(fetch_snapshots(["AAPL", "MSFT", "GOOGL", "TSLA"]))
    print(fetch_eod("AAPL", "2024-01-15"))
    print(fetch_daily_bars("AAPL", "2024-01-01", "2024-01-31"))
```

---

## Deriving "Daily % Change" from the API

The `session.change_percent` field in the unified snapshot is the canonical source for daily % change:

```
change_percent = (last_trade.price - session.previous_close) / session.previous_close * 100
```

This is computed by Massive from the prior session's official close, so it is accurate even after splits and dividends (when `adjusted=true`).

In the simulator, `previous_close` is set to the seed price at startup, and `change_percent` is calculated the same way against that baseline.

---

## Polling Strategy for FinAlly

FinAlly polls REST rather than using WebSocket:

| Scenario         | Interval   | Endpoint                              |
|-----------------|------------|---------------------------------------|
| Free tier        | 15 seconds | `/v3/snapshot?ticker.any_of=...`      |
| Starter/Developer| 15 seconds | `/v3/snapshot?ticker.any_of=...`      |
| Advanced/Business| 2 seconds  | `/v3/snapshot?ticker.any_of=...`      |

A single `/v3/snapshot` call with all watchlist tickers (max 10 in the default FinAlly config, well under the 250-ticker limit) is sufficient per polling cycle.

---

## Error Handling

```python
import requests
from requests.exceptions import HTTPError, Timeout, ConnectionError

def fetch_with_retry(url, params, retries=3):
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Timeout:
            if attempt == retries - 1:
                raise
        except HTTPError as e:
            if e.response.status_code == 429:
                # Rate limited — back off
                import time; time.sleep(2 ** attempt)
            else:
                raise
        except ConnectionError:
            if attempt == retries - 1:
                raise
    return None
```

Common HTTP status codes:
- `200 OK` — success
- `400 Bad Request` — malformed parameters
- `403 Forbidden` — invalid or missing API key
- `404 Not Found` — ticker not found or no data for date
- `429 Too Many Requests` — rate limit exceeded; use exponential backoff
