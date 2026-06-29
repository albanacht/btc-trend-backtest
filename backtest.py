"""
backtest.py — Realistic futures backtest engine.

What this does that TradingView's tester did NOT:
  - FIXED-FRACTIONAL sizing (no percent-of-equity compounding fantasy that
    turned $4k into millions on paper). Percentages here mean what they say.
  - Models Binance taker FEES on every entry/exit.
  - Models perp FUNDING charged on the open notional (default: daily approx;
    pass real funding history for precision).
  - Models LIQUIDATION: if an adverse intrabar move wipes the position margin,
    the account is marked dead — no magic recovery.

Bar-by-bar on daily data. Acts on next-bar open after a confirmed close.
"""

import numpy as np
import pandas as pd
from strategy import add_indicators, signals


def run_backtest(df: pd.DataFrame, cfg: dict) -> dict:
    df = add_indicators(df, cfg)
    df = signals(df, cfg)

    equity = cfg["initial_capital"]
    leverage = cfg["leverage"]
    fee = cfg["taker_fee"]            # e.g. 0.0004 = 0.04%
    mmr = cfg["maint_margin_rate"]    # e.g. 0.005 = 0.5%
    pos_frac = cfg["position_fraction"]
    daily_funding = cfg["daily_funding_rate"]  # signed; longs pay if positive

    side = 0            # +1 long, -1 short, 0 flat
    entry_price = 0.0
    notional = 0.0
    liq_price = None

    equity_curve = []
    trades = []
    dead = False

    rows = df.itertuples()
    prev = None
    for r in rows:
        if prev is None:
            prev = r
            equity_curve.append((r.Index, equity))
            continue

        open_px = r.open

        # ---- 1. liquidation check on this bar BEFORE anything else ----
        if side != 0 and liq_price is not None and not dead:
            hit = (side == 1 and r.low <= liq_price) or (side == -1 and r.high >= liq_price)
            if hit:
                equity = 0.0
                trades.append({"exit": r.Index, "side": side, "result": "LIQUIDATED"})
                side = 0; notional = 0.0; liq_price = None; dead = True

        if dead:
            equity_curve.append((r.Index, 0.0))
            prev = r
            continue

        # ---- 2. funding on open position (charged on notional) ----
        if side != 0:
            equity -= side * daily_funding * notional

        # ---- 3. act on PREVIOUS bar's confirmed signal, at this open ----
        # exit to flat first
        if side == 1 and prev.exit_long:
            pnl = (open_px - entry_price) / entry_price * notional
            equity += pnl - fee * notional
            trades.append({"exit": r.Index, "side": 1, "pnl": pnl})
            side = 0; notional = 0.0; liq_price = None
        elif side == -1 and prev.exit_short:
            pnl = (entry_price - open_px) / entry_price * notional
            equity += pnl - fee * notional
            trades.append({"exit": r.Index, "side": -1, "pnl": pnl})
            side = 0; notional = 0.0; liq_price = None

        # enter only from flat
        if side == 0 and equity > 0:
            new_side = 0
            if prev.long_signal:
                new_side = 1
            elif prev.short_signal:
                new_side = -1
            if new_side != 0:
                margin = equity * pos_frac
                notional = margin * leverage
                entry_price = open_px
                equity -= fee * notional
                side = new_side
                # simple liquidation price: adverse move that eats the margin
                buf = (1.0 / leverage) - mmr
                liq_price = entry_price * (1 - buf) if side == 1 else entry_price * (1 + buf)
                trades.append({"entry": r.Index, "side": side, "price": entry_price})

        # ---- 4. mark-to-market equity for the curve ----
        if side != 0:
            mtm = (side * (r.close - entry_price) / entry_price) * notional
            equity_curve.append((r.Index, equity + mtm))
        else:
            equity_curve.append((r.Index, equity))
        prev = r

    ec = pd.Series({t: v for t, v in equity_curve}).sort_index()
    return _stats(ec, trades, cfg, df)


def _stats(ec: pd.Series, trades: list, cfg: dict, df: pd.DataFrame) -> dict:
    start = cfg["initial_capital"]
    final = float(ec.iloc[-1])
    peak = ec.cummax()
    dd = (ec - peak) / peak
    max_dd = float(dd.min())

    years = (ec.index[-1] - ec.index[0]).days / 365.25
    cagr = (final / start) ** (1 / years) - 1 if final > 0 and years > 0 else -1.0

    rets = ec.pct_change().dropna()
    sharpe = float(np.sqrt(365) * rets.mean() / rets.std()) if rets.std() > 0 else 0.0

    # buy & hold over same window
    bh = df["close"].iloc[-1] / df["close"].iloc[0]
    bh_curve = start * df["close"] / df["close"].iloc[0]
    bh_dd = float(((bh_curve - bh_curve.cummax()) / bh_curve.cummax()).min())

    exits = [t for t in trades if "pnl" in t]
    wins = [t for t in exits if t["pnl"] > 0]
    liqs = [t for t in trades if t.get("result") == "LIQUIDATED"]

    return {
        "final_equity": final,
        "total_return_pct": (final / start - 1) * 100,
        "cagr_pct": cagr * 100,
        "max_drawdown_pct": max_dd * 100,
        "sharpe": sharpe,
        "num_trades": len(exits),
        "win_rate_pct": (len(wins) / len(exits) * 100) if exits else 0.0,
        "liquidated": len(liqs) > 0,
        "buy_hold_return_pct": (bh - 1) * 100,
        "buy_hold_max_dd_pct": bh_dd * 100,
        "equity_curve": ec,
    }
