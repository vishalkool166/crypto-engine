import os
import json
import logging
import pandas as pd
import numpy as np
import time
from itertools import product
from datetime import datetime, timezone

log = logging.getLogger(__name__)

DATA_DIR    = "/app/optimizer/data"
RESULTS_DIR = "/app/optimizer/results"

COINS = [
    "BTC", "ETH", "BNB", "SOL", "XRP",
    "ADA", "DOGE", "AVAX", "LINK", "UNI",
    "OP", "ARB"
]

PARAM_GRID = {
    "adx_min":      [15, 18, 20, 22, 25],
    "rsi_max_long": [65, 70, 75, 80],
    "atr_pct_max":  [3.0, 4.0, 5.0, 6.0],
    "vol_min":      [0.5, 0.6, 0.8],
}

MIN_SIGNALS  = 15
MIN_WIN_RATE = 45.0
MIN_PF       = 1.1


def _load_csv(coin: str, tf: str) -> pd.DataFrame | None:
    path = os.path.join(DATA_DIR, f"{coin}_{tf}.csv")
    if not os.path.exists(path):
        log.warning("    ❌ Missing file: %s", path)
        return None
    try:
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        df.columns = [c.lower() for c in df.columns]
        df = df.sort_index()
        log.info("    ✅ Loaded %s %s: %s candles (%s → %s)",
            coin, tf, len(df),
            str(df.index[0].date()),
            str(df.index[-1].date()),
        )
        return df
    except Exception as e:
        log.error("    ❌ Load error %s %s: %s", coin, tf, e)
        return None


def _generate_configs() -> list:
    keys   = list(PARAM_GRID.keys())
    values = list(PARAM_GRID.values())
    combos = list(product(*values))
    return [dict(zip(keys, combo)) for combo in combos]


def _score_result(result: dict) -> float:
    if result.get("total_signals", 0) < MIN_SIGNALS:
        return -1.0
    if result.get("win_rate",      0) < MIN_WIN_RATE:
        return -1.0
    if result.get("profit_factor", 0) < MIN_PF:
        return -1.0

    win_rate = result["win_rate"]
    pf       = result["profit_factor"]
    signals  = result["total_signals"]
    total_r  = result["total_r"]

    score = (
        (win_rate              * 0.35) +
        (pf                    * 0.35 * 10) +
        (min(signals, 50) / 50 * 0.15 * 100) +
        (min(total_r,  50) / 50 * 0.15 * 100)
    )
    return round(score, 4)


def _is_already_done(coin: str) -> bool:
    path = os.path.join(RESULTS_DIR, f"{coin}_done.json")
    return os.path.exists(path)


def _mark_done(coin: str, result: dict) -> None:
    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = os.path.join(RESULTS_DIR, f"{coin}_done.json")
    with open(path, "w") as f:
        json.dump(result, f, indent=2, default=str)
    log.info("    💾 Saved %s results → %s", coin, path)


def _load_done(coin: str) -> dict:
    path = os.path.join(RESULTS_DIR, f"{coin}_done.json")
    with open(path, "r") as f:
        return json.load(f)


def _print_combo_log(
    i:       int,
    total:   int,
    config:  dict,
    result:  dict,
    elapsed: float,
    passed:  bool,
) -> None:
    pct     = round(i / total * 100, 1)
    status  = "✅" if passed else "❌"
    wr      = result.get("win_rate",      0)
    pf      = result.get("profit_factor", 0)
    sigs    = result.get("total_signals", 0)
    score   = result.get("score",        -1)

    log.info(
        "    [%s/%s %s%%] %s "
        "ADX=%s RSI=%s ATR=%s VOL=%s | "
        "WR=%.1f%% PF=%.2f Sigs=%s Score=%.2f | "
        "%.2fs",
        i, total, pct, status,
        config["adx_min"],
        config["rsi_max_long"],
        config["atr_pct_max"],
        config["vol_min"],
        wr, pf, sigs, score,
        elapsed,
    )


def _print_coin_summary(coin: str, valid: list, best: dict, total_combos: int, elapsed: float):
    log.info("")
    log.info("  ┌─────────────────────────────────────────┐")
    log.info("  │  %s RESULTS                              ", coin)
    log.info("  ├─────────────────────────────────────────┤")
    log.info("  │  Total combos tested : %s",               total_combos)
    log.info("  │  Combos passed filter: %s",               len(valid))
    log.info("  │  Time taken          : %.1fs",            elapsed)
    log.info("  ├─────────────────────────────────────────┤")
    if best.get("passed_filter"):
        cfg = best["best_config"]
        res = best["best_result"]
        log.info("  │  BEST CONFIG:")
        log.info("  │    ADX min      : %s",  cfg["adx_min"])
        log.info("  │    RSI max long : %s",  cfg["rsi_max_long"])
        log.info("  │    ATR max %%   : %s",  cfg["atr_pct_max"])
        log.info("  │    Vol min      : %s",  cfg["vol_min"])
        log.info("  ├─────────────────────────────────────────┤")
        log.info("  │  BEST RESULTS:")
        log.info("  │    Win Rate     : %.1f%%", res["win_rate"])
        log.info("  │    Profit Factor: %.2f",   res["profit_factor"])
        log.info("  │    Total Signals: %s",     res["total_signals"])
        log.info("  │    Wins/Losses  : %s/%s",  res["wins"], res["losses"])
        log.info("  │    Avg RR       : %.2f",   res["avg_rr"])
        log.info("  │    Total R      : %.2f",   res["total_r"])
        log.info("  │    Score        : %.2f",   res["score"])
    else:
        log.info("  │  ⚠️  No config passed minimum filters")
        log.info("  │  Best available:")
        br = best.get("best_result", {})
        log.info("  │    Win Rate     : %.1f%%", br.get("win_rate",      0))
        log.info("  │    Profit Factor: %.2f",   br.get("profit_factor", 0))
        log.info("  │    Total Signals: %s",     br.get("total_signals", 0))
    log.info("  └─────────────────────────────────────────┘")
    log.info("")


def sweep_coin(coin: str) -> dict:
    from optimizer.backtest import prepare_indicators, run_backtest

    coin_start = time.time()

    log.info("")
    log.info("━" * 60)
    log.info("  SWEEPING: %s", coin)
    log.info("━" * 60)

    if _is_already_done(coin):
        log.info("  ⏭️  %s already completed — loading saved results", coin)
        result = _load_done(coin)
        log.info("  ✅ Loaded: WR=%.1f%% PF=%.2f Sigs=%s",
            result.get("best_result", {}).get("win_rate",      0),
            result.get("best_result", {}).get("profit_factor", 0),
            result.get("best_result", {}).get("total_signals", 0),
        )
        return result

    log.info("  📂 Loading data files...")
    df_4h = _load_csv(coin, "4h")
    df_1h = _load_csv(coin, "1h")

    if df_4h is None:
        log.error("  ❌ No 4h data for %s — skipping", coin)
        return {"coin": coin, "error": "No 4h data"}

    log.info("  🔧 Pre-calculating all indicators (done once for all combos)...")
    indicator_start = time.time()
    try:
        prepped = prepare_indicators(df_4h, df_1h)
    except Exception as e:
        log.error("  ❌ Indicator calculation failed: %s", e)
        return {"coin": coin, "error": str(e)}

    indicator_time = round(time.time() - indicator_start, 2)
    log.info("  ✅ Indicators ready in %.2fs — %s usable bars", indicator_time, len(prepped))

    configs      = _generate_configs()
    total_combos = len(configs)
    log.info("  🔁 Starting sweep: %s combinations", total_combos)
    log.info("")

    all_results  = []
    passed_count = 0
    best_so_far  = None

    for i, config in enumerate(configs, 1):
        combo_start = time.time()
        try:
            result = run_backtest(
                df_4h      = df_4h,
                df_1h      = df_1h,
                config     = config,
                coin       = coin,
                prepped_df = prepped,
            )

            if result.get("error"):
                log.warning("    [%s/%s] Error: %s", i, total_combos, result["error"])
                continue

            result["score"] = _score_result(result)
            passed          = result["score"] > 0
            combo_elapsed   = round(time.time() - combo_start, 3)

            if passed:
                passed_count += 1
                if best_so_far is None or result["score"] > best_so_far["score"]:
                    best_so_far = result
                    log.info(
                        "  🏆 NEW BEST at combo %s/%s: "
                        "WR=%.1f%% PF=%.2f Sigs=%s Score=%.2f "
                        "ADX=%s RSI=%s ATR=%s VOL=%s",
                        i, total_combos,
                        result["win_rate"],
                        result["profit_factor"],
                        result["total_signals"],
                        result["score"],
                        config["adx_min"],
                        config["rsi_max_long"],
                        config["atr_pct_max"],
                        config["vol_min"],
                    )

            _print_combo_log(i, total_combos, config, result, combo_elapsed, passed)
            all_results.append(result)

        except Exception as e:
            log.error("    [%s/%s] Exception: %s", i, total_combos, e)
            continue

    coin_elapsed = round(time.time() - coin_start, 1)

    log.info("")
    log.info("  📊 Sweep done in %.1fs — %s/%s combos passed filters",
        coin_elapsed, passed_count, total_combos
    )

    valid = [r for r in all_results if r.get("score", -1) > 0]
    valid.sort(key=lambda x: x["score"], reverse=True)

    if not valid:
        log.warning("  ⚠️  No config passed minimum filters for %s", coin)
        best_available = max(
            all_results,
            key=lambda x: (
                x.get("win_rate", 0) * 0.5 +
                x.get("profit_factor", 0) * 10 * 0.3 +
                min(x.get("total_signals", 0), 30) / 30 * 0.2 * 100
            )
        ) if all_results else {}

        final = {
            "coin":          coin,
            "best_config":   best_available.get("config",  {}),
            "best_result":   {
                "win_rate":      best_available.get("win_rate",      0),
                "profit_factor": best_available.get("profit_factor", 0),
                "total_signals": best_available.get("total_signals", 0),
                "wins":          best_available.get("wins",          0),
                "losses":        best_available.get("losses",        0),
                "avg_rr":        best_available.get("avg_rr",        0),
                "total_r":       best_available.get("total_r",       0),
                "score":         best_available.get("score",        -1),
            },
            "valid_configs": 0,
            "passed_filter": False,
            "top5":          [],
            "stats":         _summarize_all(all_results),
        }
    else:
        best = valid[0]
        top5 = valid[:5]

        final = {
            "coin":          coin,
            "best_config":   best["config"],
            "best_result": {
                "win_rate":      best["win_rate"],
                "profit_factor": best["profit_factor"],
                "total_signals": best["total_signals"],
                "wins":          best["wins"],
                "losses":        best["losses"],
                "avg_rr":        best["avg_rr"],
                "total_r":       best["total_r"],
                "score":         best["score"],
            },
            "top5": [{
                "config":        r["config"],
                "win_rate":      r["win_rate"],
                "profit_factor": r["profit_factor"],
                "total_signals": r["total_signals"],
                "score":         r["score"],
            } for r in top5],
            "valid_configs": len(valid),
            "passed_filter": True,
            "stats":         _summarize_all(all_results),
        }

        _save_top_csv(coin, valid[:20])

    _print_coin_summary(coin, valid, final, total_combos, coin_elapsed)
    _mark_done(coin, final)

    return final


def _summarize_all(results: list) -> dict:
    if not results:
        return {}

    all_wr   = [r["win_rate"]      for r in results if r.get("total_signals", 0) >= MIN_SIGNALS]
    all_pf   = [r["profit_factor"] for r in results if r.get("total_signals", 0) >= MIN_SIGNALS]
    all_sigs = [r["total_signals"] for r in results]

    if not all_wr:
        return {"avg_signals": round(sum(all_sigs) / len(all_sigs), 1) if all_sigs else 0}

    return {
        "avg_win_rate":      round(sum(all_wr)   / len(all_wr),   1),
        "max_win_rate":      round(max(all_wr),                    1),
        "min_win_rate":      round(min(all_wr),                    1),
        "avg_pf":            round(sum(all_pf)   / len(all_pf),   2),
        "max_pf":            round(max(all_pf),                    2),
        "avg_signals":       round(sum(all_sigs) / len(all_sigs),  1),
        "max_signals":       max(all_sigs),
        "configs_with_data": len(all_wr),
    }


def _save_top_csv(coin: str, valid: list) -> None:
    os.makedirs(RESULTS_DIR, exist_ok=True)
    rows = []
    for r in valid:
        rows.append({
            "coin":          coin,
            "adx_min":       r["config"]["adx_min"],
            "rsi_max_long":  r["config"]["rsi_max_long"],
            "atr_pct_max":   r["config"]["atr_pct_max"],
            "vol_min":       r["config"]["vol_min"],
            "win_rate":      r["win_rate"],
            "profit_factor": r["profit_factor"],
            "total_signals": r["total_signals"],
            "wins":          r["wins"],
            "losses":        r["losses"],
            "avg_rr":        r["avg_rr"],
            "total_r":       r["total_r"],
            "score":         r["score"],
        })
    if rows:
        path = os.path.join(RESULTS_DIR, f"{coin}_results.csv")
        pd.DataFrame(rows).to_csv(path, index=False)
        log.info("    📄 Top configs saved → %s", path)


def sweep_all() -> dict:
    os.makedirs(RESULTS_DIR, exist_ok=True)

    total_start  = time.time()
    summary      = {}
    all_best     = []
    failed       = []
    skipped      = []

    configs      = _generate_configs()
    total_combos = len(configs)

    log.info("")
    log.info("╔══════════════════════════════════════════════════════════╗")
    log.info("║           STARTING FULL PARAMETER SWEEP                 ║")
    log.info("╠══════════════════════════════════════════════════════════╣")
    log.info("║  Coins        : %s                                      ", len(COINS))
    log.info("║  Combos/coin  : %s                                      ", total_combos)
    log.info("║  Total tests  : %s                                      ", len(COINS) * total_combos)
    log.info("║  Min signals  : %s                                      ", MIN_SIGNALS)
    log.info("║  Min win rate : %s%%                                    ", MIN_WIN_RATE)
    log.info("║  Min PF       : %s                                      ", MIN_PF)
    log.info("╚══════════════════════════════════════════════════════════╝")

    already_done = [c for c in COINS if _is_already_done(c)]
    if already_done:
        log.info("")
        log.info("  ⏭️  Already completed (will skip): %s", already_done)

    for i, coin in enumerate(COINS, 1):
        log.info("")
        log.info("▶ Coin %s/%s: %s", i, len(COINS), coin)

        coins_done      = i - 1
        total_elapsed   = time.time() - total_start
        if coins_done > 0:
            avg_per_coin    = total_elapsed / coins_done
            remaining_coins = len(COINS) - coins_done
            eta_secs        = int(avg_per_coin * remaining_coins)
            eta_mins        = eta_secs // 60
            eta_secs_rem    = eta_secs % 60
            log.info("  ⏱️  Progress: %s/%s coins | Elapsed: %.0fs | ETA: %sm %ss",
                coins_done, len(COINS),
                total_elapsed,
                eta_mins, eta_secs_rem,
            )

        try:
            result        = sweep_coin(coin)
            summary[coin] = result

            if result.get("error"):
                failed.append(coin)
                log.error("  ❌ %s failed: %s", coin, result["error"])
            elif result.get("passed_filter"):
                all_best.append({
                    "coin":   coin,
                    "config": result["best_config"],
                    "result": result["best_result"],
                })
                log.info("  ✅ %s done — WR=%.1f%% PF=%.2f Sigs=%s",
                    coin,
                    result["best_result"]["win_rate"],
                    result["best_result"]["profit_factor"],
                    result["best_result"]["total_signals"],
                )
            else:
                skipped.append(coin)
                log.warning("  ⚠️  %s — no config passed filters", coin)

        except Exception as e:
            log.error("  ❌ sweep_all %s: %s", coin, e)
            failed.append(coin)
            summary[coin] = {"coin": coin, "error": str(e)}

    global_config = _derive_global_config(all_best)
    total_elapsed = round(time.time() - total_start, 1)

    log.info("")
    log.info("╔══════════════════════════════════════════════════════════╗")
    log.info("║              SWEEP COMPLETE                             ║")
    log.info("╠══════════════════════════════════════════════════════════╣")
    log.info("║  Total time   : %.1fs (%.1f mins)                       ", total_elapsed, total_elapsed / 60)
    log.info("║  Passed       : %s/%s coins                             ", len(all_best), len(COINS))
    log.info("║  No filter    : %s coins                                ", len(skipped))
    log.info("║  Failed       : %s coins                                ", len(failed))
    log.info("╚══════════════════════════════════════════════════════════╝")

    _save_final_summary(summary, all_best, global_config, failed, skipped)

    return {
        "summary":       summary,
        "all_best":      all_best,
        "global_config": global_config,
        "failed":        failed,
        "skipped":       skipped,
    }


def _derive_global_config(all_best: list) -> dict:
    if not all_best:
        return {
            "adx_min":      20,
            "rsi_max_long": 70,
            "atr_pct_max":  5.0,
            "vol_min":      0.6,
        }

    configs = [b["config"] for b in all_best]

    def _median(values):
        s = sorted(values)
        n = len(s)
        return s[n // 2] if n % 2 != 0 else (s[n//2-1] + s[n//2]) / 2

    return {
        "adx_min":      _median([c["adx_min"]      for c in configs]),
        "rsi_max_long": _median([c["rsi_max_long"]  for c in configs]),
        "atr_pct_max":  _median([c["atr_pct_max"]   for c in configs]),
        "vol_min":      _median([c["vol_min"]        for c in configs]),
    }


def _save_final_summary(
    summary:       dict,
    all_best:      list,
    global_config: dict,
    failed:        list,
    skipped:       list,
) -> None:
    os.makedirs(RESULTS_DIR, exist_ok=True)

    lines = []
    lines.append("=" * 60)
    lines.append("PARAMETER SWEEP RESULTS")
    lines.append(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("=" * 60)
    lines.append("")
    lines.append("PER COIN BEST CONFIG:")
    lines.append("-" * 60)
    lines.append(f"{'Coin':<6} {'ADX':>4} {'RSI':>4} {'ATR':>5} {'VOL':>5} {'WR%':>6} {'PF':>5} {'Sigs':>5} {'Score':>6}")
    lines.append("-" * 60)

    for b in sorted(all_best, key=lambda x: x["result"]["win_rate"], reverse=True):
        coin   = b["coin"]
        config = b["config"]
        result = b["result"]
        lines.append(
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

    lines.append("")
    lines.append("=" * 60)
    lines.append("RECOMMENDED GLOBAL CONFIG:")
    lines.append("-" * 60)
    lines.append(f"  adx_min:      {global_config['adx_min']}")
    lines.append(f"  rsi_max_long: {global_config['rsi_max_long']}")
    lines.append(f"  atr_pct_max:  {global_config['atr_pct_max']}")
    lines.append(f"  vol_min:      {global_config['vol_min']}")
    lines.append("")
    lines.append("CURRENT ENGINE CONFIG:")
    lines.append("-" * 60)
    lines.append("  adx_min:      20")
    lines.append("  rsi_max_long: 65")
    lines.append("  atr_pct_max:  4.0")
    lines.append("  vol_min:      0.8")
    lines.append("=" * 60)

    if skipped:
        lines.append(f"\nNO FILTER PASSED: {skipped}")
    if failed:
        lines.append(f"\nFAILED: {failed}")

    text = "\n".join(lines)

    txt_path = os.path.join(RESULTS_DIR, "summary.txt")
    with open(txt_path, "w") as f:
        f.write(text)

    json_path = os.path.join(RESULTS_DIR, "summary.json")
    with open(json_path, "w") as f:
        json.dump({
            "all_best":      all_best,
            "global_config": global_config,
            "failed":        failed,
            "skipped":       skipped,
            "generated_at":  datetime.now(timezone.utc).isoformat(),
        }, f, indent=2)

    log.info("📄 Summary saved → %s", txt_path)
    log.info("📄 JSON saved    → %s", json_path)