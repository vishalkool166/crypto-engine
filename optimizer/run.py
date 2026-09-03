import asyncio
import logging
import os
import sys
import time
from datetime import datetime, timezone

logging.basicConfig(
    level  = logging.INFO,
    format = "%(asctime)s — %(levelname)s — %(message)s"
)
log = logging.getLogger(__name__)

DATA_DIR    = "/app/optimizer/data"
RESULTS_DIR = "/app/optimizer/results"


def _print_banner():
    print("")
    print("=" * 60)
    print("  SIGNAL ENGINE — PARAMETER OPTIMIZER")
    print("  Finds best settings per coin using 2yr historical data")
    print("=" * 60)
    print("")


def _check_data_exists() -> bool:
    if not os.path.exists(DATA_DIR):
        return False
    coins = [
        "BTC", "ETH", "BNB", "SOL", "XRP",
        "ADA", "DOGE", "AVAX", "LINK", "UNI",
        "OP", "ARB"
    ]
    missing = []
    for coin in coins:
        for tf in ["4h", "1h"]:
            path = os.path.join(DATA_DIR, f"{coin}_{tf}.csv")
            if not os.path.exists(path):
                missing.append(f"{coin}_{tf}")
    if missing:
        log.info("Missing data files: %s", missing)
        return False
    return True


def _check_data_quality() -> dict:
    import pandas as pd
    coins = [
        "BTC", "ETH", "BNB", "SOL", "XRP",
        "ADA", "DOGE", "AVAX", "LINK", "UNI",
        "OP", "ARB"
    ]
    report = {}
    for coin in coins:
        report[coin] = {}
        for tf in ["4h", "1h"]:
            path = os.path.join(DATA_DIR, f"{coin}_{tf}.csv")
            try:
                df = pd.read_csv(path, index_col=0, parse_dates=True)
                report[coin][tf] = {
                    "candles": len(df),
                    "from":    str(df.index[0].date()),
                    "to":      str(df.index[-1].date()),
                    "ok":      len(df) >= 500,
                }
            except Exception as e:
                report[coin][tf] = {"candles": 0, "ok": False, "error": str(e)}
    return report


def _print_data_quality(report: dict):
    print("\nDATA QUALITY CHECK:")
    print("-" * 60)
    all_ok = True
    for coin, tfs in report.items():
        for tf, info in tfs.items():
            status = "✅" if info.get("ok") else "❌"
            if not info.get("ok"):
                all_ok = False
            if info.get("candles", 0) > 0:
                print(
                    f"  {status} {coin} {tf}: "
                    f"{info['candles']} candles "
                    f"({info.get('from','?')} → {info.get('to','?')})"
                )
            else:
                print(f"  {status} {coin} {tf}: NO DATA")
    print("")
    return all_ok


def _print_step(step: int, total: int, title: str):
    print("")
    print(f"[{step}/{total}] {title}")
    print("-" * 60)


def _elapsed(start: float) -> str:
    secs = int(time.time() - start)
    mins = secs // 60
    secs = secs % 60
    return f"{mins}m {secs}s"


async def step_download():
    from optimizer.download import download_all, check_existing

    existing = check_existing()
    has_data = all(
        existing.get(coin, {}).get(tf, 0) >= 500
        for coin in ["BTC", "ETH", "BNB", "SOL", "XRP",
                     "ADA", "DOGE", "AVAX", "LINK", "UNI", "OP", "ARB"]
        for tf in ["4h", "1h"]
    )

    if has_data:
        print("  Data already exists — skipping download")
        print("  Delete /app/optimizer/data/ to re-download")
        return True

    print("  Downloading 2 years of candle data from Binance...")
    print("  This will take ~10-15 minutes")
    print("")

    start  = time.time()
    result = await download_all()

    failed = [
        f"{coin} {tf}"
        for coin, tfs in result.items()
        for tf, count in tfs.items()
        if count == 0
    ]

    if failed:
        print(f"\n  ⚠️  Missing data for: {failed}")
        print("  Continuing with available data...")
    else:
        print(f"\n  ✅ All data downloaded in {_elapsed(start)}")

    return True


def step_quality_check() -> bool:
    report = _check_data_quality()
    all_ok = _print_data_quality(report)

    if not all_ok:
        print("  ⚠️  Some data has issues but continuing...")

    total_candles = sum(
        info.get("candles", 0)
        for tfs in report.values()
        for info in tfs.values()
    )
    print(f"  Total candles loaded: {total_candles:,}")
    return True


def step_sweep() -> dict:
    from optimizer.sweep import sweep_all

    print("  Testing 240 parameter combinations per coin")
    print("  12 coins × 240 combos = 2,880 total tests")
    print("  Estimated time: 20-30 minutes")
    print("  Progress will be shown below...")
    print("")

    start  = time.time()
    result = sweep_all()
    elapsed= _elapsed(start)

    print(f"\n  ✅ Sweep complete in {elapsed}")
    return result


def _print_final_report(sweep_result: dict):
    all_best      = sweep_result.get("all_best",      [])
    global_config = sweep_result.get("global_config", {})
    failed        = sweep_result.get("failed",        [])
    summary       = sweep_result.get("summary",       {})

    print("")
    print("=" * 60)
    print("  FINAL RESULTS")
    print("=" * 60)

    if all_best:
        print("\nPER COIN BEST CONFIG:")
        print("-" * 60)
        print(f"{'Coin':<6} {'ADX':>4} {'RSI':>4} {'ATR':>5} {'VOL':>5} {'WR%':>6} {'PF':>5} {'Sigs':>5} {'Score':>6}")
        print("-" * 60)

        for b in sorted(all_best, key=lambda x: x["result"]["win_rate"], reverse=True):
            coin   = b["coin"]
            config = b["config"]
            result = b["result"]
            print(
                f"{coin:<6} "
                f"{config['adx_min']:>4} "
                f"{config['rsi_max_long']:>4} "
                f"{config['atr_pct_max']:>5} "
                f"{config['vol_min']:>5} "
                f"{result['win_rate']:>6.1f} "
                f"{result['profit_factor']:>5.2f} "
                f"{result['total_signals']:>5} "
                f"{result['score']:>6.2f}"
            )

    coins_no_filter = [
        coin for coin, r in summary.items()
        if not r.get("passed_filter") and not r.get("error")
    ]

    if coins_no_filter:
        print(f"\n⚠️  These coins had NO config passing minimum filters:")
        for coin in coins_no_filter:
            r  = summary[coin]
            br = r.get("best_result", {})
            print(
                f"  {coin}: best WR={br.get('win_rate',0):.1f}% "
                f"Signals={br.get('total_signals',0)} "
                f"PF={br.get('profit_factor',0):.2f}"
            )
        print("  → These coins may need looser filters or more data")

    if failed:
        print(f"\n❌ Failed coins: {failed}")

    print("")
    print("=" * 60)
    print("RECOMMENDED GLOBAL CONFIG:")
    print("(median across all coins that passed filters)")
    print("-" * 60)
    print(f"  adx_min:      {global_config.get('adx_min',      20)}")
    print(f"  rsi_max_long: {global_config.get('rsi_max_long', 70)}")
    print(f"  atr_pct_max:  {global_config.get('atr_pct_max',  5.0)}")
    print(f"  vol_min:      {global_config.get('vol_min',       0.6)}")
    print("=" * 60)

    print("")
    print("CURRENT ENGINE CONFIG (for comparison):")
    print("-" * 60)
    print("  adx_min:      20   (trend_min_adx)")
    print("  rsi_max_long: 65   (rsi scorer max)")
    print("  atr_pct_max:  4.0  (volatile threshold)")
    print("  vol_min:      0.8  (volume_ratio_min)")
    print("=" * 60)

    print("")
    print("OUTPUT FILES:")
    print("-" * 60)
    print(f"  Per coin CSV:  {RESULTS_DIR}/<COIN>_results.csv")
    print(f"  Summary text:  {RESULTS_DIR}/summary.txt")
    print(f"  Summary JSON:  {RESULTS_DIR}/summary.json")
    print("=" * 60)
    print("")


def _print_next_steps(sweep_result: dict):
    global_config = sweep_result.get("global_config", {})

    print("NEXT STEPS:")
    print("-" * 60)
    print("1. Review results above")
    print("2. Compare recommended vs current config")
    print("3. If results look good, update these values:")
    print("")
    print("   In engines/trend/direction.py:")
    print(f"     trend_min_adx: {global_config.get('adx_min', 20)}")
    print("")
    print("   In engines/regime/detector.py:")
    print(f"     atr_pct volatile threshold: {global_config.get('atr_pct_max', 5.0)}")
    print("")
    print("   In engines/scoring/scorer.py:")
    print(f"     rsi max for LONG: {global_config.get('rsi_max_long', 70)}")
    print("")
    print("   In config.py HYBRID_ENGINE:")
    print(f"     volume_ratio_min: {global_config.get('vol_min', 0.6)}")
    print("")
    print("4. Read full details in:")
    print(f"   {RESULTS_DIR}/summary.txt")
    print("=" * 60)
    print("")


async def main():
    _print_banner()

    total_start = time.time()
    total_steps = 3

    _print_step(1, total_steps, "DOWNLOADING HISTORICAL DATA")
    await step_download()

    _print_step(2, total_steps, "DATA QUALITY CHECK")
    step_quality_check()

    _print_step(3, total_steps, "RUNNING PARAMETER SWEEP")
    sweep_result = step_sweep()

    _print_final_report(sweep_result)
    _print_next_steps(sweep_result)

    print(f"Total time: {_elapsed(total_start)}")
    print("Done! ✅")


if __name__ == "__main__":
    sys.path.insert(0, "/app")
    asyncio.run(main())