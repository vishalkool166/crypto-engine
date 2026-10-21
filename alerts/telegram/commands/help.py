from alerts.telegram.client import send


async def cmd_help() -> None:
    await send(
        "🧭 *Signal Engine — Operator Menu*\n\n*Commands*\n"
        "📡 /ping — confirm the command reached your server\n"
        "🩺 /health — check data, Redis, and scanner freshness\n"
        "📊 /status — engine and execution mode\n"
        "🔎 /scan — request a guarded market scan\n"
        "💼 /trades — inspect open account positions\n"
        "🧭 /position SYMBOL — inspect one position\n"
        "📈 /journey ID — view a trade's recorded path\n"
        "🏁 /performance — review recorded results\n"
        "🇮🇳 /india · /orb · /indianstats — Indian-market research\n"
        "🌐 /coin SYMBOL · /brief — market research\n"
        "🧪 /backtest SYMBOL — cached-data research replay\n\n"
        "Use /start or /help to see this menu."
    )
