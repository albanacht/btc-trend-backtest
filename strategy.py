"""
strategy.py — Gated SMA200 trend logic.

This is the SINGLE source of truth for the strategy rules. The backtester
imports it, and the live bot will import the EXACT same file later, so what
you validate here is literally what you run. No Pine-vs-Python divergence.

Rules (same as the TradingView version):
  - Regime gate: only act when a trend exists (ADX > threshold AND SMA sloping
    the right way). Otherwise FLAT. This is what keeps it out of chop.
  - Confirmation band: require close beyond SMA by an ATR multiple, not a bare
    touch — suppresses micro-whipsaws.
  - Flat-then-reenter: exit to FLAT when price loses the SMA; only enter the
    opposite side on a fresh confirmed signal. Never a violent direct flip.
"""

import pandas as pd
import numpy as np


def add_indicators(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    out = df.copy()
    n_sma = cfg["sma_len"]
    n_atr = cfg["atr_len"]
    n_adx = cfg["adx_len"]
    slope = cfg["slope_len"]

    # SMA
    out["sma"] = out["close"].rolling(n_sma).mean()

    # ATR (Wilder)
    prev_close = out["close"].shift(1)
    tr = pd.concat([
        out["high"] - out["low"],
        (out["high"] - prev_close).abs(),
        (out["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    out["atr"] = tr.ewm(alpha=1 / n_atr, adjust=False).mean()

    # ADX (Wilder)
    up_move = out["high"].diff()
    down_move = -out["low"].diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    atr_adx = tr.ewm(alpha=1 / n_adx, adjust=False).mean()
    plus_di = 100 * pd.Series(plus_dm, index=out.index).ewm(alpha=1 / n_adx, adjust=False).mean() / atr_adx
    minus_di = 100 * pd.Series(minus_dm, index=out.index).ewm(alpha=1 / n_adx, adjust=False).mean() / atr_adx
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    out["adx"] = dx.ewm(alpha=1 / n_adx, adjust=False).mean()

    # bands and regime
    out["upper"] = out["sma"] + cfg["atr_mult"] * out["atr"]
    out["lower"] = out["sma"] - cfg["atr_mult"] * out["atr"]
    out["sma_rising"] = out["sma"] > out["sma"].shift(slope)
    out["sma_falling"] = out["sma"] < out["sma"].shift(slope)
    out["trending"] = out["adx"] > cfg["adx_thresh"]
    return out


def signals(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Adds target-state columns. We evaluate on the CONFIRMED close and act
    on the next bar's open in the backtester, so there is no lookahead."""
    out = df.copy()
    out["long_signal"] = (
        cfg["allow_longs"] & (out["close"] > out["upper"])
        & out["sma_rising"] & out["trending"]
    )
    out["short_signal"] = (
        cfg["allow_shorts"] & (out["close"] < out["lower"])
        & out["sma_falling"] & out["trending"]
    )
    out["exit_long"] = out["close"] < out["sma"]
    out["exit_short"] = out["close"] > out["sma"]
    return out
