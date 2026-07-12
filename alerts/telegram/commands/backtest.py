import asyncio
import logging
from alerts.telegram.client     import send
from alerts.telegram.formatters import now_ist
from config import cfg

log = logging.getLogger(__name__)


async def cmd_backtest(coin: str) -> None:
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
        await send(
            f"📊 *Backtest — {coin}USDT*\n\n"
            f"Period: `{result.get('period_start')} → {result.get('period_end')}`\n\n"
            f"Signals: `{result.get('total_signals', 0)}` · "
            f"Trades: `{result.get('total_trades', 0)}`\n"
            f"WR: `{result.get('win_rate', 0)}%` · "
            f"PnL: `${result.get('total_pnl', 0)}`\n"
            f"Max DD: `{result.get('max_drawdown', 0)}%` · "
            f"TP1 hit: `{pb.get('tp1_hit_rate', 0)}%`\n\n"
            f"A+: `{bg.get('A+', {}).get('win_rate', 0)}% WR` · "
            f"`{bg.get('A+', {}).get('trades', 0)} trades`\n"
            f"A:  `{bg.get('A',  {}).get('win_rate', 0)}% WR` · "
            f"`{bg.get('A',  {}).get('trades', 0)} trades`\n"
        )
    except asyncio.TimeoutError:
        await send("❌ Backtest timed out after 120s")
    except Exception as e:
        await send(f"❌ Backtest error: `{e}`")


async def cmd_backfill(coin: str | None = None) -> None:
    await send(f"⏳ *Backfill started for {coin or 'all coins'}...*")
    try:
        from backfill import run_backfill
        asyncio.create_task(run_backfill(coins=[coin] if coin else None))
    except Exception as e:
        await send(f"❌ Backfill failed: `{e}`")