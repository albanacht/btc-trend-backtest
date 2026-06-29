# BTC Trend Sleeve — Backtest

Honest backtest of the gated SMA200 trend strategy on BTC, with the realism
TradingView's tester left out: **fixed-fractional sizing** (no compounding
fantasy), **Binance fees**, **perp funding**, and **liquidation modelling**.

`strategy.py` is the single source of truth for the rules — the live bot will
import the same file, so backtest and live behaviour cannot diverge.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

No API key needed — it pulls public Binance market data.

## What to look at

The headline return is the seductive number; **max drawdown is the decision
number.** A trend overlay's job is to give a *lower* drawdown than buy & hold
(BTC's ~80%), even if total return is lower. "Less return, much less drawdown"
can be the better thing to actually hold.

If `LIQUIDATED: True`, the run is void — the account died before any recovery.
Lower the leverage in `run.py` and re-run.

## Knobs (in `run.py` CONFIG)

- `leverage` — try 1, 2, 3. Watch drawdown move faster than return.
- `position_fraction` — fraction of equity risked per trade.
- `start` / `end` — set a window for walk-forward (tune on one, verify on another).
- `atr_mult`, `adx_thresh`, `slope_len` — the regime gate / confirmation knobs.

## Honest limitations

- Daily funding is an average approximation unless you wire in full funding
  history per bar.
- Liquidation model is simplified (single-position, linear) — conservative
  enough to flag blow-ups, not exchange-exact.
- A good backtest is necessary, not sufficient. Paper-trade on Binance testnet
  before a single real USDT.
