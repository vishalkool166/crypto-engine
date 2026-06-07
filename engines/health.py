from datetime import datetime, timezone
import time

HEALTHY     = "HEALTHY"
WARNING     = "WARNING"
INVALIDATED = "INVALIDATED"

_MINOR_WARNING_KEYS = [
    "btc neutral",
    "oi unclear",
    "near entry",
    "approaching ob"
]

_state_first_seen: dict = {}
_DEBOUNCE_SECONDS = 120


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

    retest_zone = retest.get("zone")
    if retest_zone:
        zone_top    = retest_zone.get("top", 0)
        zone_bottom = retest_zone.get("bottom", 0)
        if is_long and current_price < zone_bottom * 0.995:
            failures.append("Retest zone broken — price closed below demand zone")
        elif not is_long and current_price > zone_top * 1.005:
            failures.append("Retest zone broken — price closed above supply zone")
        else:
            checks.append("Retest zone holding")
    else:
        checks.append("No retest zone to monitor")

    struct_bias = d1d.get("structure", {}).get("struct_bias", "neutral")
    d1_cls      = d1d.get("trend",     {}).get("cls",          "neutral")

    if is_long:
        if struct_bias == "bear":
            failures.append("Daily structure flipped bearish — original thesis invalidated")
        elif d1_cls == "bear":
            warnings.append("Daily trend weakening — monitor closely")
        else:
            checks.append("Structure intact")
    else:
        if struct_bias == "bull":
            failures.append("Daily structure flipped bullish — original thesis invalidated")
        elif d1_cls == "bull":
            warnings.append("Daily trend weakening — monitor closely")
        else:
            checks.append("Structure intact")

    if btc_data:
        btc_cls = btc_data.get("trend", {}).get("cls", "neutral")
        if is_long and btc_cls == "bear":
            warnings.append("BTC flipped bearish — headwind for long")
        elif not is_long and btc_cls == "bull":
            warnings.append("BTC flipped bullish — headwind for short")
        elif btc_cls == "neutral":
            warnings.append("BTC neutral — no confirmation")
        else:
            checks.append(f"BTC {btc_cls}ish — aligned")
    else:
        checks.append("BTC data unavailable — skipped")

    oi_label = oi_matrix.get("primary_label", "")
    if "exhaust" in oi_label.lower():
        warnings.append(f"OI exhaustion — {oi_label} — momentum may be fading")
    elif "confirm" in oi_label.lower():
        checks.append(f"OI supporting — {oi_label}")
    else:
        warnings.append(f"OI unclear — {oi_label}")

    move_pct = (
        (current_price - entry) / entry * 100
        if is_long
        else (entry - current_price) / entry * 100
    )

    if move_pct > 0:
        checks.append(f"Price {move_pct:.2f}% in profit direction")
    elif move_pct > -0.5:
        checks.append(f"Price near entry ({move_pct:.2f}%) — normal fluctuation")
    elif move_pct > -2.0:
        warnings.append(f"Price {abs(move_pct):.2f}% against entry — monitor SL")
    else:
        warnings.append(f"Price {abs(move_pct):.2f}% against entry — approaching SL territory")

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
            failures.append("Entry order block mitigated — institutional zone used up")
        elif nearest and nearest.get("in_zone"):
            checks.append("Price still in OB zone")
        elif nearest and nearest.get("approaching"):
            checks.append("Price approaching OB zone")

    major_warnings = [w for w in warnings if not _is_minor(w)]
    minor_warnings = [w for w in warnings if     _is_minor(w)]

    if failures:
        raw_state = INVALIDATED
    elif len(major_warnings) >= 1:
        raw_state = WARNING
    elif len(minor_warnings) >= 3:
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
        "summary":         _build_summary(state, checks, warnings, failures, original_thesis),
        "move_pct":        round(move_pct, 2),
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
        lines.append("\nThesis weakening — monitor closely.\nNo action required yet.")
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

    if state == INVALIDATED:
        lines.append("\n_Thesis invalidated. Use /close if you want to exit._")
    elif state == WARNING:
        lines.append("\n_Thesis weakening. Monitor position._")

    return "\n".join(lines)