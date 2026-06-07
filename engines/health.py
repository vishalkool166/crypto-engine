from datetime import datetime, timezone


# ═══════════════════════════════════════════════════════
# HEALTH STATES
# ═══════════════════════════════════════════════════════
HEALTHY     = "HEALTHY"
WARNING     = "WARNING"
INVALIDATED = "INVALIDATED"


# ═══════════════════════════════════════════════════════
# TRADE HEALTH ENGINE
# Monitors the original trade thesis after entry.
# Tracks: retest validity, structure, BTC alignment,
# OI support, major warning conditions.
# Does NOT invent new exit logic.
# Does NOT auto-close trades.
# Informs only.
# ═══════════════════════════════════════════════════════
def check_trade_health(
    trade,
    current_price:  float,
    d1d:            dict,
    d4h:            dict,
    btc_data:       dict,
    oi_matrix:      dict,
    retest:         dict,
    sweep:          dict,
    original_thesis: str = ""
) -> dict:

    checks   = []
    warnings = []
    failures = []

    direction = trade.direction
    entry     = trade.entry_price
    is_long   = direction == "LONG"

    # ── 1. RETEST VALIDITY ──
    # Original retest zone should still be respected.
    # If price has closed back through it — thesis broken.
    retest_zone = retest.get("zone")
    if retest_zone:
        zone_top    = retest_zone.get("top", 0)
        zone_bottom = retest_zone.get("bottom", 0)

        if is_long and current_price < zone_bottom * 0.995:
            failures.append(
                "Retest zone broken — "
                "price closed below demand zone"
            )
        elif not is_long and current_price > zone_top * 1.005:
            failures.append(
                "Retest zone broken — "
                "price closed above supply zone"
            )
        else:
            checks.append("Retest zone holding")
    else:
        checks.append("No retest zone to monitor")

    # ── 2. STRUCTURE VALIDITY ──
    # Daily structure bias should still align with direction.
    struct_bias = d1d.get("structure", {}).get(
        "struct_bias", "neutral"
    )
    d1_cls = d1d.get("trend", {}).get("cls", "neutral")

    if is_long:
        if struct_bias == "bear":
            failures.append(
                "Daily structure flipped bearish — "
                "original thesis invalidated"
            )
        elif d1_cls == "bear":
            warnings.append(
                "Daily trend weakening — "
                "monitor closely"
            )
        else:
            checks.append("Structure intact")
    else:
        if struct_bias == "bull":
            failures.append(
                "Daily structure flipped bullish — "
                "original thesis invalidated"
            )
        elif d1_cls == "bull":
            warnings.append(
                "Daily trend weakening — "
                "monitor closely"
            )
        else:
            checks.append("Structure intact")

    # ── 3. BTC ALIGNMENT ──
    # BTC should not have flipped against the trade.
    if btc_data:
        btc_cls = btc_data.get("trend", {}).get(
            "cls", "neutral"
        )
        if is_long and btc_cls == "bear":
            warnings.append(
                "BTC flipped bearish — "
                "headwind for long"
            )
        elif not is_long and btc_cls == "bull":
            warnings.append(
                "BTC flipped bullish — "
                "headwind for short"
            )
        elif btc_cls == "neutral":
            warnings.append("BTC neutral — no confirmation")
        else:
            checks.append(f"BTC {btc_cls}ish — aligned")

    # ── 4. OI SUPPORT ──
    # OI exhaustion after entry is a warning.
    oi_label = oi_matrix.get("primary_label", "")
    if "exhaust" in oi_label.lower():
        warnings.append(
            f"OI exhaustion — {oi_label} — "
            f"momentum may be fading"
        )
    elif "confirm" in oi_label.lower():
        checks.append(f"OI supporting — {oi_label}")
    else:
        warnings.append(f"OI unclear — {oi_label}")

    # ── 5. PRICE VS ENTRY ──
    # Not a block — context only.
    move_pct = (
        (current_price - entry) / entry * 100
        if is_long
        else (entry - current_price) / entry * 100
    )

    if move_pct > 0:
        checks.append(
            f"Price {move_pct:.2f}% in profit direction"
        )
    else:
        warnings.append(
            f"Price {abs(move_pct):.2f}% against entry — "
            f"monitor SL"
        )

    # ── 6. FUNDING SPIKE POST ENTRY ──
    # Extreme funding after entry is a warning.
    funding = oi_matrix.get("funding_warning", "")
    if funding:
        warnings.append(funding)

    # ── DETERMINE HEALTH STATE ──
    if failures:
        state = INVALIDATED
    elif len(warnings) >= 3:
        state = WARNING
    elif len(warnings) >= 1:
        state = WARNING
    else:
        state = HEALTHY

    # ── BUILD SUMMARY ──
    summary = _build_summary(
        state, checks, warnings, failures,
        original_thesis
    )

    return {
        "state":            state,
        "checks":           checks,
        "warnings":         warnings,
        "failures":         failures,
        "summary":          summary,
        "move_pct":         round(move_pct, 2),
        "checked_at":       datetime.now(timezone.utc).isoformat(),
        "is_healthy":       state == HEALTHY,
        "is_warning":       state == WARNING,
        "is_invalidated":   state == INVALIDATED,
        "original_thesis":  original_thesis
    }


def _build_summary(
    state:           str,
    checks:          list,
    warnings:        list,
    failures:        list,
    original_thesis: str
) -> str:

    lines = [f"Trade Status: {state}\n"]

    if original_thesis:
        lines.append(f"Original Thesis:\n{original_thesis}\n")

    if failures:
        lines.append("Invalidation Reasons:")
        for f in failures:
            lines.append(f"  ✘ {f}")

    if warnings:
        lines.append("\nWarnings:")
        for w in warnings:
            lines.append(f"  ⚠ {w}")

    if checks:
        lines.append("\nHealthy:")
        for c in checks:
            lines.append(f"  ✔ {c}")

    if state == INVALIDATED:
        lines.append(
            "\nOriginal thesis no longer valid.\n"
            "Consider closing or reducing position.\n"
            "Bot will NOT auto-close — your decision."
        )
    elif state == WARNING:
        lines.append(
            "\nThesis weakening — monitor closely.\n"
            "No action required yet."
        )
    else:
        lines.append("\nThesis intact. Hold position.")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════
# HEALTH ALERT MESSAGE
# Formatted for Telegram send().
# Called from trade manager monitor loop.
# ═══════════════════════════════════════════════════════
def format_health_alert(health: dict, coin: str) -> str:
    state = health["state"]

    emoji = (
        "✅" if state == HEALTHY     else
        "⚠️" if state == WARNING     else
        "🚨"
    )

    lines = [
        f"{emoji} *Trade Health — {coin}*\n",
        f"Status: `{state}`\n"
    ]

    if health["failures"]:
        lines.append("*Invalidated:*")
        for f in health["failures"]:
            lines.append(f"✘ {f}")

    if health["warnings"]:
        lines.append("\n*Warnings:*")
        for w in health["warnings"]:
            lines.append(f"⚠ {w}")

    if health["checks"] and state == HEALTHY:
        lines.append("\n*Healthy:*")
        for c in health["checks"]:
            lines.append(f"✔ {c}")

    lines.append(
        f"\nMove: `{health['move_pct']:+.2f}%` from entry"
    )

    if state == INVALIDATED:
        lines.append(
            "\n_Thesis invalidated. "
            "Use /close if you want to exit._"
        )
    elif state == WARNING:
        lines.append(
            "\n_Thesis weakening. "
            "Monitor position._"
        )

    return "\n".join(lines)