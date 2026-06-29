"""
data.py — Pull BTC daily OHLCV from an exchange that works from Colab.

Binance geo-blocks Google/Colab servers (HTTP 451), so we use Coinbase by
default and fall back to Kraken / Bitstamp. All reachable from Colab, no key.

Note: BTC/USD history on Coinbase starts ~2015-2016 (plenty for a daily SMA200
strategy across multiple cycles).
"""

import pandas as pd

# exchanges to try, in order — all Colab-friendly, public data, no key needed
_EXCHANGES = [
    ("coinbase", "BTC/USD"),
    ("kraken",   "BTC/USD"),
    ("bitstamp", "BTC/USD"),
]


def fetch_ohlcv(symbol=None, timeframe="1d", since_year=2017):
    import ccxt
    last_err = None
    for ex_id, default_symbol in _EXCHANGES:
        sym = symbol or default_symbol
        try:
            ex = getattr(ccxt, ex_id)({"enableRateLimit": True})
            since = ex.parse8601(f"{since_year}-01-01T00:00:00Z")
            all_rows = []
            while True:
                batch = ex.fetch_ohlcv(sym, timeframe=timeframe, since=since, limit=300)
                if not batch:
                    break
                all_rows += batch
                since = batch[-1][0] + 1
                if len(batch) < 300:
                    break
            if not all_rows:
                raise RuntimeError("no rows returned")
            df = pd.DataFrame(all_rows, columns=["ts", "open", "high", "low", "close", "volume"])
            df["ts"] = pd.to_datetime(df["ts"], unit="ms")
            df = df.set_index("ts").drop_duplicates()
            print(f"Data source: {ex_id} ({sym}) - {len(df)} daily bars "
                  f"from {df.index[0].date()} to {df.index[-1].date()}")
            return df
        except Exception as e:
            last_err = e
            print(f"  {ex_id} failed ({str(e)[:60]}...), trying next...")
            continue
    raise RuntimeError(f"All exchanges failed. Last error: {last_err}")


def fetch_avg_funding(symbol="BTC/USDT:USDT"):
    """Funding history is a Binance-perp concept and Binance is geo-blocked from
    Colab, so return a sane default here (~0.01%/8h, a neutral-market value).
    On your own machine or a VPS you can wire in real Binance funding later.
    Bump this if you want to stress-test funding drag."""
    return 0.0001
