"""
data.py — Pull BTC daily OHLCV (and optionally funding history) from Binance
via ccxt. No API key needed for public market data.
"""

import pandas as pd


def fetch_ohlcv(symbol="BTC/USDT", timeframe="1d", since_year=2017):
    import ccxt
    ex = ccxt.binance({"enableRateLimit": True})
    since = ex.parse8601(f"{since_year}-01-01T00:00:00Z")
    all_rows = []
    while True:
        batch = ex.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=1000)
        if not batch:
            break
        all_rows += batch
        since = batch[-1][0] + 1
        if len(batch) < 1000:
            break
    df = pd.DataFrame(all_rows, columns=["ts", "open", "high", "low", "close", "volume"])
    df["ts"] = pd.to_datetime(df["ts"], unit="ms")
    df = df.set_index("ts").drop_duplicates()
    return df


def fetch_avg_funding(symbol="BTC/USDT:USDT"):
    """Rough average 8h funding rate over available history, as a sanity input.
    For a precise run, pull full funding history and apply per-bar instead."""
    import ccxt
    ex = ccxt.binance({"enableRateLimit": True, "options": {"defaultType": "future"}})
    hist = ex.fetch_funding_rate_history(symbol, limit=1000)
    if not hist:
        return 0.0001  # ~0.01% per 8h fallback
    rates = [h["fundingRate"] for h in hist if h.get("fundingRate") is not None]
    return sum(rates) / len(rates) if rates else 0.0001
