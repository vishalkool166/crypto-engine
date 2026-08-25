import asyncio
import logging
from alerts.telegram.client     import send
from alerts.telegram.formatters import now_ist
from config import cfg

log = logging.getLogger(__name__)

_backtest_running = False


async def cmd_backtest(coin: str) -> None:
    global _backtest_running

    if _backtest_running:
        await send(f"⏳ Backtest already running — please wait.")
        return

    _backtest_running = True
    from backtest.engine import run_backtest
    await send(f"⏳ Running backtest for `{coin}`...")
    try:
        loop   = asyncio.get_running_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: run_backtest(coin=coin, capital=cfg.CAPITAL, leverage=10)
            ),
            timeout=120.0,
        )
        if "error" in result:
            await send(f"❌ Backtest failed: `{result['error']}`")
            return

        bg = result.get("by_grade", {})
        pb = result.get("phase_breakdown", {})
        wf = result.get("walk_forward", {})

        train = wf.get("train", {})
        test  = wf.get("test",  {})
        deg   = wf.get("oos_degradation", 0)

        await send(
            f"📊 *Backtest — {coin}USDT*\n\n"
            f"Period: `{result.get('period_start')} → {result.get('period_end')}`\n\n"
            f"Signals: `{result.get('total_signals', 0)}` · "
            f"Trades: `{result.get('total_trades', 0)}`\n"
            f"WR: `{result.get('win_rate', 0)}%` · "
            f"PnL: `${result.get('total_pnl', 0)}`\n"
            f"Max DD: `{result.get('max_drawdown', 0)}%` · "
            f"PF: `{result.get('profit_factor', 0)}`\n\n"
            f"*Walk-Forward:*\n"
            f"Train: `{train.get('period','')}` → "
            f"`{train.get('trades',0)}` trades `{train.get('win_rate',0)}%` WR\n"
            f"Test:  `{test.get('period','')}` → "
            f"`{test.get('trades',0)}` trades `{test.get('win_rate',0)}%` WR\n"
            f"OOS degradation: `{deg}%`\n\n"
            f"A+: `{bg.get('A+', {}).get('win_rate', 0)}% WR` · "
            f"`{bg.get('A+', {}).get('trades', 0)} trades`\n"
            f"A:  `{bg.get('A',  {}).get('win_rate', 0)}% WR` · "
            f"`{bg.get('A',  {}).get('trades', 0)} trades`\n"
        )
    except asyncio.TimeoutError:
        await send("❌ Backtest timed out after 120s")
    except Exception as e:
        await send(f"❌ Backtest error: `{e}`")
    finally:
        _backtest_running = False


async def cmd_backfill(coin: str | None = None) -> None:
    from backfill import (
        run_backfill, run_backfill_single,
        get_candle_summary, TARGET_CANDLES, TIMEFRAMES
    )

    if coin:
        await send(f"⏳ *Backfilling {coin}...*\n\nTimeframes: `{', '.join(TIMEFRAMES)}`")
        try:
            asyncio.create_task(run_backfill_single(coin))
            await send(
                f"✅ *Backfill started for {coin}*\n\n"
                f"Running in background.\n"
                f"Targets: " + " · ".join(f"`{tf}:{TARGET_CANDLES[tf]}`" for tf in TIMEFRAMES)
            )
        except Exception as e:
            await send(f"❌ Backfill failed: `{e}`")
        return

    await send(
        f"⏳ *Full Backfill Started*\n\n"
        f"Coins: `{len(__import__('config').cfg.COINS)}`\n"
        f"Timeframes: `{', '.join(TIMEFRAMES)}`\n"
        f"Targets: " + " · ".join(f"`{tf}:{TARGET_CANDLES[tf]}`" for tf in TIMEFRAMES) + "\n\n"
        f"_Disabled coins will be purged automatically._\n"
        f"_Running in background — takes 15-30 minutes._"
    )

    try:
        asyncio.create_task(run_backfill(purge_disabled=True))
    except Exception as e:
        await send(f"❌ Backfill failed: `{e}`")


async def cmd_candle_status() -> None:
    from backfill import get_candle_summary, TARGET_CANDLES, TIMEFRAMES
    from data.store import get_candle_count
    from config import cfg

    await send("⏳ Checking candle status...")

    try:
        summary  = get_candle_summary()
        lines    = [f"📊 *Candle Status*\n"]
        complete = 0
        total    = 0

        for coin in cfg.COINS[:15]:
            coin_data = summary.get(coin, {})
            coin_ok   = True
            coin_line = f"`{coin}`: "
            tf_parts  = []

            for tf in ["1w", "4h", "1h", "15m"]:
                data  = coin_data.get(tf, {})
                count = data.get("count", 0)
                tgt   = data.get("target", 0)

                if tf == "1w" and count < 200:
                    tf_parts.append(f"{tf}:⚠️{count}")
                    coin_ok = False
                elif tf != "1w" and not data.get("complete"):
                    tf_parts.append(f"{tf}:❌{count}/{tgt}")
                    coin_ok = False
                else:
                    tf_parts.append(f"{tf}:✅")

                total += 1
                if data.get("complete") or (tf == "1w" and count >= 200):
                    complete += 1

            status = "✅" if coin_ok else "⚠️"
            lines.append(f"{status} {coin_line}{' '.join(tf_parts)}")

        if len(cfg.COINS) > 15:
            lines.append(f"\n_...and {len(cfg.COINS)-15} more coins_")

        pct_complete = round(complete / total * 100, 1) if total > 0 else 0
        lines.append(f"\n*Overall: `{complete}/{total}` ({pct_complete}%) complete*")

        if pct_complete < 100:
            lines.append(f"\n_Run /backfill to complete missing data_")

        await send("\n".join(lines))

    except Exception as e:
        log.error("cmd_candle_status: %s", e)
        await send(f"❌ Candle status failed: `{e}`")