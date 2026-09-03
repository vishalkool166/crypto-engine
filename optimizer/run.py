import asyncio
import logging
import os
import sys
import time
from datetime import datetime, timezone

logging.basicConfig(
    level   = logging.INFO,
    format  = "%(asctime)s — %(levelname)s — %(message)s",
    handlers= [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("/app/optimizer/optimizer.log"),
    ]
)
log = logging.getLogger(__name__)

DATA_DIR    = "/app/optimizer/data"
RESULTS_DIR = "/app/optimizer/results"

COINS = [
    "BTC", "ETH", "BNB", "SOL", "XRP",
    "ADA", "DOGE", "AVAX", "LINK", "UNI",
    "OP", "ARB"
]


def _elapsed(start: float) -> str:
    secs = int(time.time() - start)
    mins = secs // 60
    secs = secs % 60
    return f"{mins}m {secs}s"


def _print_banner():
    log.info("")
    log.info("╔══════════════════════════════════════════════════════════╗")
    log.info("║        SIGNAL ENGINE — PARAMETER OPTIMIZER              ║")
    log.info("║   Finds best settings per coin using 2yr history        ║")
    log.info("╠══════════════════════════════════════════════════════════╣")
    log.info("║  Started : %s                    ", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
    log.info("║  Log file: /app/optimizer/optimizer.log                 ║")
    log.info("╚══════════════════════════════════════════════════════════╝")
    log.info("")


def _check_existing_data() -> dict:
    if not os.path.exists(DATA_DIR):
        return {}
    existing = {}
    for coin in COINS:
        existing[coin] = {}
        for tf in ["4h", "1h"]:
            path = os.path.join(DATA_DIR, f"{coin}_{tf}.csv")
            if os.path.exists(path):
                try:
                    import pandas as pd
                    df = pd.read_csv(path, index_col=0, parse_dates=True)
                    existing[coin][tf] = {
                        "candles": len(df),
                        "from":    str(df.index[0].date()),
                        "to":      str(df.index[-1].date()),
                        "ok":      len(df) >= 500,
                    }
                except Exception as e:
                    existing[coin][tf] = {"candles": 0, "ok": False, "error": str(e)}
            else:
                existing[coin][tf] = {"candles": 0, "ok": False}
    return existing


def _all_data_ready(existing: dict) -> bool:
    for coin in COINS:
        for tf in ["4h", "1h"]:
            if not existing.get(coin, {}).get(tf, {}).get("ok", False):
                return False
    return True


def _check_resume_status() -> dict:
    from optimizer.sweep import _is_already_done
    status = {}
    for coin in COINS:
        status[coin] = _is_already_done(coin)
    return status


def _print_resume_status(status: dict):
    done    = [c for c, v in status.items() if v]
    pending = [c for c, v in status.items() if not v]

    log.info("  RESUME STATUS:")
    log.info("  ✅ Already done (%s): %s", len(done),    done    if done    else "none")
    log.info("  ⏳ Pending      (%s): %s", len(pending), pending if pending else "none")
    log.info("")

    return len(done), len(pending)


def _print_data_status(existing: dict):
    log.info("  DATA STATUS:")
    log.info("  %-6s  %-8s  %-8s  %-12s  %-12s", "Coin", "4h", "1h", "4h Range", "1h Range")
    log.info("  " + "-" * 55)

    all_ok = True
    for coin in COINS:
        d4h = existing.get(coin, {}).get("4h", {})
        d1h = existing.get(coin, {}).get("1h", {})

        s4h    = "✅" if d4h.get("ok") else "❌"
        s1h    = "✅" if d1h.get("ok") else "❌"
        r4h    = f"{d4h.get('from','?')} → {d4h.get('to','?')}" if d4h.get("candles", 0) > 0 else "missing"
        r1h    = f"{d1h.get('from','?')} → {d1h.get('to','?')}" if d1h.get("candles", 0) > 0 else "missing"
        c4h    = d4h.get("candles", 0)
        c1h    = d1h.get("candles", 0)

        if not d4h.get("ok") or not d1h.get("ok"):
            all_ok = False

        log.info(
            "  %-6s  %s %-5s  %s %-5s  %-20s  %-20s",
            coin, s4h, c4h, s1h, c1h, r4h, r1h
        )

    log.info("")
    total = sum(
        v.get("candles", 0)
        for tfs in existing.values()
        for v in tfs.values()
    )
    log.info("  Total candles: %s", f"{total:,}")
    log.info("")
    return all_ok


async def step_1_download(force: bool = False) -> bool:
    log.info("━" * 60)
    log.info("STEP 1/3 — DOWNLOAD HISTORICAL DATA")
    log.info("━" * 60)

    existing = _check_existing_data()
    all_ok   = _all_data_ready(existing)

    if all_ok and not force:
        log.info("  ✅ All data already downloaded — skipping")
        log.info("  💡 To re-download: delete /app/optimizer/data/")
        _print_data_status(existing)
        return True

    if not all_ok:
        missing = [
            f"{coin} {tf}"
            for coin in COINS
            for tf in ["4h", "1h"]
            if not existing.get(coin, {}).get(tf, {}).get("ok", False)
        ]
        log.info("  Missing data: %s", missing)

    log.info("  📥 Starting download from Binance Futures...")
    log.info("  ⏱️  Estimated time: 10-15 minutes")
    log.info("")

    from optimizer.download import download_all
    start  = time.time()
    result = await download_all()

    failed = [
        f"{coin} {tf}"
        for coin, tfs in result.items()
        for tf, count in tfs.items()
        if count == 0
    ]

    log.info("")
    if failed:
        log.warning("  ⚠️  Missing after download: %s", failed)
        log.warning("  Continuing with available data...")
    else:
        log.info("  ✅ All data downloaded in %s", _elapsed(start))

    existing = _check_existing_data()
    _print_data_status(existing)
    return True


def step_2_quality_check() -> bool:
    log.info("━" * 60)
    log.info("STEP 2/3 — DATA QUALITY CHECK")
    log.info("━" * 60)

    existing = _check_existing_data()
    all_ok   = _print_data_status(existing)

    if not all_ok:
        log.warning("  ⚠️  Some data has issues — results may be incomplete")
    else:
        log.info("  ✅ All data looks good")

    log.info("")
    return True


def step_3_sweep() -> dict:
    log.info("━" * 60)
    log.info("STEP 3/3 — PARAMETER SWEEP")
    log.info("━" * 60)
    log.info("")

    resume_status        = _check_resume_status()
    done_count, pending  = _print_resume_status(resume_status)

    if pending == 0:
        log.info("  ✅ All coins already completed!")
        log.info("  💡 To re-run: delete /app/optimizer/results/*_done.json")
        log.info("")
        from optimizer.sweep import sweep_all
        return sweep_all()

    from optimizer.sweep import _generate_configs
    combos = len(_generate_configs())

    log.info("  SWEEP PLAN:")
    log.info("  %-6s  %-10s  %-10s", "Coin", "Status", "Combos")
    log.info("  " + "-" * 30)
    for coin in COINS:
        status = "⏭️  skip" if resume_status[coin] else f"⏳ {combos} combos"
        log.info("  %-6s  %s", coin, status)
    log.info("")
    log.info("  Total new tests: %s", pending * combos)
    log.info("  Est. time:       %s mins", round(pending * combos * 0.01 / 60 * 1000))
    log.info("")

    from optimizer.sweep import sweep_all
    start  = time.time()
    result = sweep_all()

    log.info("")
    log.info("  ✅ Sweep complete in %s", _elapsed(start))
    return result


def _print_final_report(sweep_result: dict):
    all_best      = sweep_result.get("all_best",      [])
    global_config = sweep_result.get("global_config", {})
    failed        = sweep_result.get("failed",        [])
    skipped       = sweep_result.get("skipped",       [])
    summary       = sweep_result.get("summary",       {})

    log.info("")
    log.info("╔══════════════════════════════════════════════════════════╗")
    log.info("║                  FINAL RESULTS                         ║")
    log.info("╚══════════════════════════════════════════════════════════╝")

    if all_best:
        log.info("")
        log.info("PER COIN BEST CONFIG:")
        log.info("%-6s  %4s  %4s  %5s  %5s  %6s  %5s  %5s  %6s",
            "Coin", "ADX", "RSI", "ATR", "VOL", "WR%", "PF", "Sigs", "Score"
        )
        log.info("-" * 60)

        for b in sorted(all_best, key=lambda x: x["result"]["win_rate"], reverse=True):
            coin   = b["coin"]
            config = b["config"]
            result = b["result"]
            log.info(
                "%-6s  %4s  %4s  %5s  %5s  %6.1f  %5.2f  %5s  %6.2f",
                coin,
                config["adx_min"],
                config["rsi_max_long"],
                config["atr_pct_max"],
                config["vol_min"],
                result["win_rate"],
                result["profit_factor"],
                result["total_signals"],
                result["score"],
            )

    if skipped:
        log.info("")
        log.info("⚠️  NO CONFIG PASSED FILTERS FOR:")
        for coin in skipped:
            r  = summary.get(coin, {})
            br = r.get("best_result", {})
            log.info(
                "  %s: best WR=%.1f%% PF=%.2f Sigs=%s",
                coin,
                br.get("win_rate",      0),
                br.get("profit_factor", 0),
                br.get("total_signals", 0),
            )
        log.info("  → These coins may need looser filters")

    if failed:
        log.info("")
        log.info("❌ FAILED COINS: %s", failed)

    log.info("")
    log.info("╔══════════════════════════════════════════════════════════╗")
    log.info("║            RECOMMENDED GLOBAL CONFIG                   ║")
    log.info("╠══════════════════════════════════════════════════════════╣")
    log.info("║  adx_min      : %-5s  (current: 20)                   ", global_config.get("adx_min",      20))
    log.info("║  rsi_max_long : %-5s  (current: 65)                   ", global_config.get("rsi_max_long", 70))
    log.info("║  atr_pct_max  : %-5s  (current: 4.0)                  ", global_config.get("atr_pct_max",  5.0))
    log.info("║  vol_min      : %-5s  (current: 0.8)                  ", global_config.get("vol_min",       0.6))
    log.info("╚══════════════════════════════════════════════════════════╝")

    log.info("")
    log.info("╔══════════════════════════════════════════════════════════╗")
    log.info("║                  NEXT STEPS                            ║")
    log.info("╠══════════════════════════════════════════════════════════╣")
    log.info("║  1. Review results above                                ║")
    log.info("║  2. Check detailed CSVs in /app/optimizer/results/      ║")
    log.info("║  3. If happy with results update these files:           ║")
    log.info("║                                                         ║")
    log.info("║  engines/trend/direction.py                             ║")
    log.info("║    trend_min_adx → %s                                  ", global_config.get("adx_min", 20))
    log.info("║                                                         ║")
    log.info("║  engines/regime/detector.py                             ║")
    log.info("║    atr_pct volatile threshold → %s                     ", global_config.get("atr_pct_max", 5.0))
    log.info("║                                                         ║")
    log.info("║  engines/scoring/scorer.py                              ║")
    log.info("║    rsi max for LONG → %s                               ", global_config.get("rsi_max_long", 70))
    log.info("║                                                         ║")
    log.info("║  config.py HYBRID_ENGINE                                ║")
    log.info("║    volume_ratio_min → %s                               ", global_config.get("vol_min", 0.6))
    log.info("╚══════════════════════════════════════════════════════════╝")

    log.info("")
    log.info("OUTPUT FILES:")
    log.info("  Per coin:  /app/optimizer/results/<COIN>_results.csv")
    log.info("  Summary:   /app/optimizer/results/summary.txt")
    log.info("  JSON:      /app/optimizer/results/summary.json")
    log.info("  Full log:  /app/optimizer/optimizer.log")
    log.info("")


async def main():
    _print_banner()
    total_start = time.time()

    os.makedirs(DATA_DIR,    exist_ok=True)
    os.makedirs(RESULTS_DIR, exist_ok=True)

    await step_1_download()
    step_2_quality_check()
    sweep_result = step_3_sweep()

    _print_final_report(sweep_result)

    log.info("━" * 60)
    log.info("TOTAL TIME: %s", _elapsed(total_start))
    log.info("DONE ✅")
    log.info("━" * 60)
    log.info("")


if __name__ == "__main__":
    sys.path.insert(0, "/app")
    asyncio.run(main())