from datetime import datetime, timezone
import time

HEALTHY     = "HEALTHY"
WARNING     = "WARNING"
INVALIDATED = "INVALIDATED"

_MINOR_WARNING_KEYS = [
    "btc neutral",
    "oi unclear",
    "near entry",
    "approaching ob",
    "minor headwind",
    "weak trend",
    "no directional conflict",
]

_DEBOUNCE_SECONDS = 120

_state_first_seen: dict = {}


def _is_minor(warning: str) -> bool:
    w = warning.lower()
    return any(k in w for k in _MINOR_WARNING_KEYS)


def _debounce_state(new_state: str, current_state: str) -> str:
    if new_state == INVALIDATED:
        _state_first_seen.clear()
        return INVALIDATED

    if new_state == current_state:
        _state_first_seen.pop(new_state, None)
        return current_state

    now = time.time()
    if new_state not in _state_first_seen:
        _state_first_seen[new_state] = now
        return current_state

    if time.time() - _state_first_seen[new_state] >= _DEBOUNCE_SECONDS:
        _state_first_seen.pop(new_state, None)
        return new_state

    return current_state


def check_trade_health(
    trade,
    current_price:   float,
    d1d:             dict,
    d4h:             dict,
    btc_data:        dict,
    oi_matrix:       dict,
    retest:          dict,
    sweep:           dict,
    original_thesis: str = "",
    current_state:   str = HEALTHY
) -> dict:

    checks   = []
    warnings = []
    failures = []

    direction = trade.direction
    entry     = trade.entry_price
    is_long   = direction == "LONG"

    atr = d1d.get("atr") or (entry * 0.015 if entry else 0)

    retest_zone = retest.get("zone")
    if retest_zone:
        zone_top    = retest_zone.get("top", 0)
        zone_bottom = retest_zone.get("bottom", 0)
        atr_buffer  = atr * 0.3 if atr > 0 else zone_bottom * 0.005

        if is_long and current_price < zone_bottom - atr_buffer:
            failures.append(
                f"Retest zone broken — price closed below demand zone "
                f"by more than {atr_buffer:.4f}"
            )
        elif not is_long and current_price > zone_top + atr_buffer:
            failures.append(
                f"Retest zone broken — price closed above supply zone "
                f"by more than {atr_buffer:.4f}"
            )
        else:
            checks.append("Retest zone holding")
    else:
        checks.append("No retest zone to monitor")

    structure_events = d1d.get("structure", {}).get("events", [])

    bos_against_thesis   = False
    choch_against_thesis = False

    for event in structure_events:
        event_type = event.get("type", "")
        event_bias = event.get("bias", "")
        event_desc = event.get("desc", "")

        if event_type == "BOS":
            if is_long and event_bias == "bear":
                failures.append(
                    f"Bearish BOS formed — {event_desc or 'swing low broken'} "
                    f"— long thesis invalidated"
                )
                bos_against_thesis = True
            elif not is_long and event_bias == "bull":
                failures.append(
                    f"Bullish BOS formed — {event_desc or 'swing high broken'} "
                    f"— short thesis invalidated"
                )
                bos_against_thesis = True

        elif event_type == "CHoCH":
            if is_long and event_bias == "bear":
                warnings.append(
                    f"Bearish CHoCH detected — {event_desc or 'potential reversal'} "
                    f"— monitor closely"
                )
                choch_against_thesis = True
            elif not is_long and event_bias == "bull":
                warnings.append(
                    f"Bullish CHoCH detected — {event_desc or 'potential reversal'} "
                    f"— monitor closely"
                )
                choch_against_thesis = True

    if not bos_against_thesis and not choch_against_thesis:
        checks.append("No adverse BOS/CHoCH detected")

    struct_bias = d1d.get("structure", {}).get("struct_bias", "neutral")
    d1_cls      = d1d.get("trend",     {}).get("cls",          "neutral")

    if is_long:
        if struct_bias == "bear" and not bos_against_thesis:
            failures.append(
                "Daily structure flipped bearish — original thesis invalidated"
            )
        elif d1_cls == "bear":
            warnings.append("Daily trend weakening — monitor closely")
        else:
            checks.append("D1 structure intact")
    else:
        if struct_bias == "bull" and not bos_against_thesis:
            failures.append(
                "Daily structure flipped bullish — original thesis invalidated"
            )
        elif d1_cls == "bull":
            warnings.append("Daily trend weakening — monitor closely")
        else:
            checks.append("D1 structure intact")

    d4h_struct_bias = d4h.get("structure", {}).get("struct_bias", "neutral")
    d4h_cls         = d4h.get("trend",     {}).get("cls",         "neutral")

    if is_long:
        if d4h_struct_bias == "bear":
            warnings.append("4H structure bearish — conflicts with long thesis")
        elif d4h_cls == "bear":
            warnings.append("4H trend bearish — monitor for continuation")
        else:
            checks.append(f"4H structure aligned — {d4h_struct_bias}")
    else:
        if d4h_struct_bias == "bull":
            warnings.append("4H structure bullish — conflicts with short thesis")
        elif d4h_cls == "bull":
            warnings.append("4H trend bullish — monitor for continuation")
        else:
            checks.append(f"4H structure aligned — {d4h_struct_bias}")

    if btc_data:
        btc_cls = btc_data.get("trend", {}).get("cls", "neutral")
        btc_adx = btc_data.get("adx", 0) or 0

        if is_long and btc_cls == "bear":
            if btc_adx > 25:
                warnings.append(
                    f"BTC strongly bearish (ADX {btc_adx:.0f}) "
                    f"— significant headwind for long"
                )
            else:
                checks.append(
                    f"BTC bearish but weak trend (ADX {btc_adx:.0f}) "
                    f"— minor headwind"
                )
        elif not is_long and btc_cls == "bull":
            if btc_adx > 25:
                warnings.append(
                    f"BTC strongly bullish (ADX {btc_adx:.0f}) "
                    f"— significant headwind for short"
                )
            else:
                checks.append(
                    f"BTC bullish but weak trend (ADX {btc_adx:.0f}) "
                    f"— minor headwind"
                )
        elif btc_cls == "neutral":
            checks.append("BTC neutral — no directional conflict")
        else:
            checks.append(f"BTC {btc_cls}ish — aligned with thesis")
    else:
        checks.append("BTC data unavailable — skipped")

    oi_label = oi_matrix.get("primary_label", "")
    if "exhaust" in oi_label.lower():
        warnings.append(
            f"OI exhaustion — {oi_label} — momentum may be fading"
        )
    elif "confirm" in oi_label.lower():
        checks.append(f"OI supporting — {oi_label}")
    else:
        checks.append(f"OI unclear — {oi_label}")

    move_pct = (
        (current_price - entry) / entry * 100
        if is_long
        else (entry - current_price) / entry * 100
    )

    adverse_move = (
        (entry - current_price) if is_long
        else (current_price - entry)
    )
    adverse_atr = adverse_move / atr if atr > 0 else 0

    if adverse_atr <= 0:
        checks.append(f"Price {move_pct:.2f}% in profit direction")
    elif adverse_atr < 0.3:
        checks.append(
            f"Price {abs(move_pct):.2f}% adverse "
            f"({adverse_atr:.1f}x ATR) — normal fluctuation"
        )
    elif adverse_atr < 0.7:
        warnings.append(
            f"Price {abs(move_pct):.2f}% adverse "
            f"({adverse_atr:.1f}x ATR) — monitor SL"
        )
    else:
        warnings.append(
            f"Price {abs(move_pct):.2f}% adverse "
            f"({adverse_atr:.1f}x ATR) — approaching SL territory"
        )

    funding = oi_matrix.get("funding_warning", "")
    if funding:
        warnings.append(funding)

    ob_data = d4h.get("order_blocks", {})
    if ob_data:
        nearest = (
            ob_data.get("nearest_bull") if is_long
            else ob_data.get("nearest_bear")
        )
        if nearest and nearest.get("mitigated"):
            struct_also_failed = (
                struct_bias == "bear" if is_long
                else struct_bias == "bull"
            )
            if struct_also_failed:
                failures.append(
                    "Entry OB mitigated AND structure failed "
                    "— institutional zone used up, thesis invalidated"
                )
            else:
                warnings.append(
                    "Entry OB mitigated — zone used up, "
                    "monitor structure for continuation"
                )
        elif nearest and nearest.get("in_zone"):
            checks.append("Price still in OB zone")
        elif nearest and nearest.get("approaching"):
            checks.append("Price approaching OB zone")

    major_warnings = [w for w in warnings if not _is_minor(w)]
    minor_warnings = [w for w in warnings if     _is_minor(w)]

    if failures:
        raw_state = INVALIDATED
    elif len(major_warnings) >= 2:
        raw_state = WARNING
    elif len(major_warnings) == 1 and len(minor_warnings) >= 2:
        raw_state = WARNING
    elif len(minor_warnings) >= 4:
        raw_state = WARNING
    else:
        raw_state = HEALTHY

    state = _debounce_state(raw_state, current_state)

    return {
        "state":           state,
        "raw_state":       raw_state,
        "checks":          checks,
        "warnings":        warnings,
        "major_warnings":  major_warnings,
        "minor_warnings":  minor_warnings,
        "failures":        failures,
        "summary":         _build_summary(
            state, checks, warnings,
            failures, original_thesis
        ),
        "move_pct":        round(move_pct, 2),
        "adverse_atr":     round(adverse_atr, 2),
        "atr_used":        round(atr, 6),
        "checked_at":      datetime.now(timezone.utc).isoformat(),
        "is_healthy":      state == HEALTHY,
        "is_warning":      state == WARNING,
        "is_invalidated":  state == INVALIDATED,
        "original_thesis": original_thesis
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


def format_health_alert(health: dict, coin: str) -> str:
    state = health["state"]
    emoji = (
        "✅" if state == HEALTHY else
        "⚠️" if state == WARNING else
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

    lines.append(f"\nMove: `{health['move_pct']:+.2f}%` from entry")

    if health.get("adverse_atr", 0) > 0:
        lines.append(f"Adverse: `{health['adverse_atr']:.1f}x ATR` from entry")

    if state == INVALIDATED:
        lines.append("\n_Thesis invalidated. Use /close if you want to exit._")
    elif state == WARNING:
        lines.append("\n_Thesis weakening. Monitor position._")

    return "\n".join(lines)