"""
run.py — Run the backtest and print honest numbers + save an equity-curve plot.

    python run.py

Edit CONFIG below to change leverage, sizing, dates, parameters.
"""

import pandas as pd
from data import fetch_ohlcv, fetch_avg_funding
from backtest import run_backtest

CONFIG = {
    # --- strategy params (match the Pine version) ---
    "sma_len": 200,
    "atr_len": 14,
    "atr_mult": 0.5,
    "adx_len": 14,
    "adx_thresh": 20,
    "slope_len": 20,
    "allow_longs": True,
    "allow_shorts": True,

    # --- account & realism (the stuff TradingView faked) ---
    "initial_capital": 4000.0,
    "position_fraction": 1.0,     # fraction of equity used as margin per trade
    "leverage": 1.0,              # <-- try 1, 2, 3. Watch what it does to drawdown.
    "taker_fee": 0.0004,          # 0.04% Binance futures taker
    "maint_margin_rate": 0.005,   # 0.5%
    "daily_funding_rate": None,   # None => auto-fetch avg; or set e.g. 0.0003

    # --- window ---
    "since_year": 2017,           # Binance BTC/USDT starts ~Aug 2017
    "start": "2021-01-01",                # e.g. "2021-01-01" for walk-forward
    "end": None,
}


def main():
    print("Fetching BTC/USDT daily from Binance...")
    df = fetch_ohlcv(since_year=CONFIG["since_year"])

    if CONFIG["start"]:
        df = df[df.index >= pd.Timestamp(CONFIG["start"])]
    if CONFIG["end"]:
        df = df[df.index <= pd.Timestamp(CONFIG["end"])]

    if CONFIG["daily_funding_rate"] is None:
        avg_8h = fetch_avg_funding()
        CONFIG["daily_funding_rate"] = avg_8h * 3  # 3 funding windows per day
        print(f"Auto funding: {avg_8h*100:.4f}% per 8h -> "
              f"{CONFIG['daily_funding_rate']*100:.4f}%/day")

    res = run_backtest(df, CONFIG)

    print("\n" + "=" * 48)
    print(f"  Window:        {df.index[0].date()} -> {df.index[-1].date()}")
    print(f"  Leverage:      {CONFIG['leverage']}x")
    print("-" * 48)
    print(f"  Total return:  {res['total_return_pct']:>10.1f}%")
    print(f"  CAGR:          {res['cagr_pct']:>10.1f}%")
    print(f"  Max drawdown:  {res['max_drawdown_pct']:>10.1f}%   <-- the number that matters")
    print(f"  Sharpe:        {res['sharpe']:>10.2f}")
    print(f"  Trades:        {res['num_trades']:>10d}")
    print(f"  Win rate:      {res['win_rate_pct']:>10.1f}%")
    print(f"  LIQUIDATED:    {str(res['liquidated']):>10}")
    print("-" * 48)
    print(f"  Buy & hold:    {res['buy_hold_return_pct']:>10.1f}%  "
          f"(max dd {res['buy_hold_max_dd_pct']:.1f}%)")
    print("=" * 48)
    print("\nRead it as: does the strategy give acceptable drawdown vs buy & hold,")
    print("not just higher return. And if LIQUIDATED is True, the run is void.")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        ax = res["equity_curve"].plot(figsize=(11, 5), title="Strategy equity (fixed sizing)")
        ax.set_ylabel("USDT")
        plt.tight_layout()
        plt.savefig("equity_curve.png", dpi=110)
        print("\nSaved equity_curve.png")
    except Exception as e:
        print(f"(plot skipped: {e})")


if __name__ == "__main__":
    main()
