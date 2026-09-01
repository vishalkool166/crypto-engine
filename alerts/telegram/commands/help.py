from alerts.telegram.client import send


async def cmd_help() -> None:
    await send(
        "🤖 *Signal Engine v5 — Commands*\n\n"
        "*TRADING*\n"
        "/status   — bot status\n"
        "/scan     — manual scan\n"
        "/trades   — open positions\n"
        "/position ETH — trade detail\n"
        "/balance  — account balance\n"
        "/profit   — profit summary\n\n"
        "*MARKET*\n"
        "/coin ETH · /funding · /fear · /brief\n\n"
        "*PERFORMANCE*\n"
        "/pnl · /daily · /stats · /history\n"
        "/backtest BTC · /performance\n\n"
        "*DATA*\n"
        "/backfill BTC · /candles · /mode\n\n"
        "*🇮🇳 INDIAN MARKET*\n"
        "/india       — market status + signals\n"
        "/orb         — BANKNIFTY ORB levels\n"
        "/indianstats — strategy performance\n\n"
        "/help — this message"
    )