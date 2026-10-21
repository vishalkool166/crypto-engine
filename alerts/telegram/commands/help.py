from alerts.telegram.client import send


async def cmd_help() -> None:
    await send(
        "🤖 *Signal Engine — Commands*\n\n"
        "*TRADING*\n"
        "/status   — bot status\n"
        "/scan     — manual scan\n"
        "/trades   — open positions\n"
        "/position ETH — trade detail\n"
        "/journey 42 — recorded price path for trade 42\n"
        "/balance  — account balance\n"
        "/profit   — profit summary\n\n"
        "*MARKET*\n"
        "/coin ETH · /btc · /funding · /fear · /brief\n\n"
        "*PERFORMANCE*\n"
        "/pnl · /daily · /stats · /history · /grade\n"
        "/backtest ETH · /performance · /queue\n\n"
        "*DATA*\n"
        "/backfill ETH · /candles · /mode · /health\n"
        "/pending · /discard 5 — content drafts\n\n"
        "*🇮🇳 INDIAN MARKET*\n"
        "/india       — market status + signals\n"
        "/orb         — BANKNIFTY ORB levels\n"
        "/indianstats — strategy performance\n\n"
        "/help — this message"
    )
