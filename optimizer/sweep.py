import os
import json
import logging
import pandas as pd
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

MIN_SIGNALS     = 15
MIN_WIN_RATE    = 45.0
MIN_PF          = 1.1


def _load_csv(coin: str, tf: str) -> pd.DataFrame | None:
    path = os.path.join(DATA_DIR, f"{coin}_{tf}.csv")
    if not os.path.exists(path):
        log.warning("Missing file: %s", path)
        return None
    try:
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        df.columns = [c.lower() for c in df.columns]
        df = df.sort_index()
        log.info("Loaded %s %s: %s candles", coin, tf, len(df))
        return df
    except Exception as e:
        log.error("Load error %s %s: %s", coin, tf, e)
        return None


def _generate_configs() -> list:
    keys   = list(PARAM_GRID.keys())
    values = list(PARAM_GRID.values())
    combos = list(product(*values))
    configs = []
    for combo in combos:
        configs.append(dict(zip(keys, combo)))
    return configs


def _score_result(result: dict) -> float:
    if result.get("total_signals", 0) < MIN_SIGNALS:
        return -1.0
    if result.get("win_rate", 0) < MIN_WIN_RATE:
        return -1.0
    if result.get("profit_factor", 0) < MIN_PF:
        return -1.0

    win_rate = result["win_rate"]
    pf       = result["profit_factor"]
    signals  = result["total_signals"]
    total_r  = result["total_r"]

    score = (
        (win_rate  * 0.35) +
        (pf        * 0.35 * 10) +
        (min(signals, 50) / 50 * 0.15 * 100) +
        (min(total_r, 50) / 50 * 0.15 * 100)
    )

    return round(score, 4)


def sweep_coin(coin: str) -> dict:
    from optimizer.backtest import run_backtest

    log.info("=" * 50)
    log.info("Sweeping %s", coin)
    log.info("=" * 50)

    df_4h = _load_csv(coin, "4h")
    df_1h = _load_csv(coin, "1h")

    if df_4h is None:
        log.error("No 4h data for %s — skipping", coin)
        return {"coin": coin, "error": "No 4h data"}

    configs      = _generate_configs()
    total_combos = len(configs)
    log.info("%s: testing %s parameter combinations", coin, total_combos)

    all_results = []

    for i, config in enumerate(configs, 1):
        if i % 50 == 0:
            log.info(
                "%s: progress %s/%s (%.0f%%)",
                coin, i, total_combos,
                i / total_combos * 100
            )

        try:
            result = run_backtest(
                df_4h  = df_4h,
                df_1h  = df_1h,
                config = config,
                coin   = coin,
            )

            if result.get("error"):
                continue

            result["score"] = _score_result(result)
            all_results.append(result)

        except Exception as e:
            log.error("Sweep error %s config=%s: %s", coin, config, e)
            continue

    if not all_results:
        log.warning("%s: no valid results", coin)
        return {"coin": coin, "error": "No valid results"}

    valid = [r for r in all_results if r["score"] > 0]
    log.info(
        "%s: %s/%s configs passed minimum filters",
        coin, len(valid), total_combos
    )

    if not valid:
        best = max(all_results, key=lambda x: x.get("win_rate", 0))
        log.warning(
            "%s: no config passed filters — best win_rate=%.1f%% signals=%s",
            coin,
            best.get("win_rate", 0),
            best.get("total_signals", 0),
        )
        return {
            "coin":          coin,
            "best_config":   best["config"],
            "best_result":   best,
            "valid_configs": 0,
            "passed_filter": False,
            "all_results":   _summarize_results(all_results),
        }

    valid.sort(key=lambda x: x["score"], reverse=True)
    best = valid[0]

    top5 = valid[:5]

    log.info(
        "%s: BEST config found — WR=%.1f%% PF=%.2f Signals=%s Score=%.2f",
        coin,
        best["win_rate"],
        best["profit_factor"],
        best["total_signals"],
        best["score"],
    )
    log.info("%s: best config = %s", coin, best["config"])

    _save_coin_results(coin, valid, best)

    return {
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
        "all_results":   _summarize_results(all_results),
    }


def _summarize_results(results: list) -> dict:
    if not results:
        return {}

    win_rates = [r["win_rate"]      for r in results if r.get("total_signals", 0) >= MIN_SIGNALS]
    pfs       = [r["profit_factor"] for r in results if r.get("total_signals", 0) >= MIN_SIGNALS]
    signals   = [r["total_signals"] for r in results]

    if not win_rates:
        return {
            "avg_signals": round(sum(signals) / len(signals), 1) if signals else 0,
        }

    return {
        "avg_win_rate":      round(sum(win_rates) / len(win_rates), 1),
        "max_win_rate":      round(max(win_rates), 1),
        "min_win_rate":      round(min(win_rates), 1),
        "avg_pf":            round(sum(pfs) / len(pfs), 2),
        "max_pf":            round(max(pfs), 2),
        "avg_signals":       round(sum(signals) / len(signals), 1),
        "max_signals":       max(signals),
        "configs_with_data": len(win_rates),
    }


def _save_coin_results(coin: str, valid: list, best: dict) -> None:
    os.makedirs(RESULTS_DIR, exist_ok=True)

    rows = []
    for r in valid[:20]:
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
        df = pd.DataFrame(rows)
        path = os.path.join(RESULTS_DIR, f"{coin}_results.csv")
        df.to_csv(path, index=False)
        log.info("Saved %s results → %s", coin, path)


def sweep_all() -> dict:
    os.makedirs(RESULTS_DIR, exist_ok=True)

    summary     = {}
    all_best    = []
    failed      = []

    log.info("=" * 60)
    log.info("STARTING PARAMETER SWEEP")
    log.info("Coins:       %s", len(COINS))
    log.info("Combos/coin: %s", len(_generate_configs()))
    log.info("Total tests: %s", len(COINS) * len(_generate_configs()))
    log.info("=" * 60)

    for i, coin in enumerate(COINS, 1):
        log.info("--- Coin %s/%s: %s ---", i, len(COINS), coin)
        try:
            result       = sweep_coin(coin)
            summary[coin]= result

            if result.get("error"):
                failed.append(coin)
            elif result.get("passed_filter"):
                all_best.append({
                    "coin":   coin,
                    "config": result["best_config"],
                    "result": result["best_result"],
                })
        except Exception as e:
            log.error("sweep_all %s: %s", coin, e)
            failed.append(coin)
            summary[coin] = {"coin": coin, "error": str(e)}

    global_config = _derive_global_config(all_best)
    _save_summary(summary, all_best, global_config, failed)

    return {
        "summary":       summary,
        "all_best":      all_best,
        "global_config": global_config,
        "failed":        failed,
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
        return s[n // 2] if n % 2 != 0 else (s[n//2 - 1] + s[n//2]) / 2

    return {
        "adx_min":      _median([c["adx_min"]      for c in configs]),
        "rsi_max_long": _median([c["rsi_max_long"]  for c in configs]),
        "atr_pct_max":  _median([c["atr_pct_max"]   for c in configs]),
        "vol_min":      _median([c["vol_min"]        for c in configs]),
    }


def _save_summary(
    summary:       dict,
    all_best:      list,
    global_config: dict,
    failed:        list,
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

    for b in all_best:
        coin   = b["coin"]
        config = b["config"]
        result = b["result"]
        lines.append(f"\n{coin}:")
        lines.append(f"  ADX min:      {config['adx_min']}")
        lines.append(f"  RSI max long: {config['rsi_max_long']}")
        lines.append(f"  ATR max %:    {config['atr_pct_max']}")
        lines.append(f"  Vol min:      {config['vol_min']}")
        lines.append(f"  Win Rate:     {result['win_rate']}%")
        lines.append(f"  Profit Factor:{result['profit_factor']}")
        lines.append(f"  Signals:      {result['total_signals']}")
        lines.append(f"  Avg RR:       {result['avg_rr']}")
        lines.append(f"  Total R:      {result['total_r']}")

    lines.append("")
    lines.append("=" * 60)
    lines.append("RECOMMENDED GLOBAL CONFIG (median of all coins):")
    lines.append("-" * 60)
    lines.append(f"  adx_min:      {global_config['adx_min']}")
    lines.append(f"  rsi_max_long: {global_config['rsi_max_long']}")
    lines.append(f"  atr_pct_max:  {global_config['atr_pct_max']}")
    lines.append(f"  vol_min:      {global_config['vol_min']}")
    lines.append("=" * 60)

    if failed:
        lines.append("")
        lines.append(f"FAILED COINS: {failed}")

    coins_no_filter = [
        coin for coin, r in summary.items()
        if not r.get("passed_filter") and not r.get("error")
    ]
    if coins_no_filter:
        lines.append("")
        lines.append(f"COINS WITH NO CONFIG PASSING FILTERS: {coins_no_filter}")
        lines.append("(showing best available for these coins)")
        for coin in coins_no_filter:
            r = summary[coin]
            if r.get("best_result"):
                br = r["best_result"]
                lines.append(f"  {coin}: WR={br.get('win_rate',0)}% Signals={br.get('total_signals',0)}")

    text = "\n".join(lines)
    path = os.path.join(RESULTS_DIR, "summary.txt")
    with open(path, "w") as f:
        f.write(text)

    json_path = os.path.join(RESULTS_DIR, "summary.json")
    with open(json_path, "w") as f:
        json.dump({
            "all_best":      all_best,
            "global_config": global_config,
            "failed":        failed,
            "generated_at":  datetime.now(timezone.utc).isoformat(),
        }, f, indent=2)

    print("\n" + text)
    log.info("Summary saved → %s", path)
    log.info("JSON saved    → %s", json_path)