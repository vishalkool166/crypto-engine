from alerts.telegram.client import send


async def cmd_ml() -> None:
    await send(
        "🤖 *ML Status*\n\n"
        "ML system is currently disabled.\n"
        "The engine uses momentum strategy.\n"
        "ML will be re-enabled after sufficient trade data is collected."
    )


async def cmd_adaptations() -> None:
    await send(
        "🧠 *Adaptations*\n\n"
        "Adaptation system is currently disabled.\n"
        "Strategy parameters are fixed."
    )


async def cmd_freeze() -> None:
    await send("Adaptation system is disabled.")


async def cmd_unfreeze() -> None:
    await send("Adaptation system is disabled.")


async def cmd_rollback(parameter: str) -> None:
    await send("Adaptation system is disabled.")


async def cmd_approve(rec_id_str: str) -> None:
    await send("Adaptation system is disabled.")


async def cmd_reject(rec_id_str: str) -> None:
    await send("Adaptation system is disabled.")


async def cmd_version() -> None:
    from config import cfg
    await send(
        f"⚙️ *System Version*\n\n"
        f"Version: `{cfg.SYSTEM_VERSION}`\n"
        f"Strategy: Momentum\n"
        f"ADX min: `{cfg.HYBRID_ENGINE.get('trend_min_adx', 18)}`\n"
        f"EMA buffer: `{cfg.HYBRID_ENGINE.get('trend_ema_buffer_atr_mult', 0.05)}`\n"
        f"SL min: `{cfg.HYBRID_ENGINE.get('sl_min_pct', 0.3)}%`\n"
        f"SL max: `{cfg.HYBRID_ENGINE.get('sl_max_pct', 5.0)}%`\n"
        f"TP RR: `{cfg.HYBRID_ENGINE.get('tp1_min_rr', 2.5)}R`"
    )


async def cmd_analysis() -> None:
    await send("Analysis system is disabled.")