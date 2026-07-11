from engines.session import get_session


def build_trade_thesis(
    sweep:        dict,
    displacement: dict,
    retest:       dict,
    d1d:          dict,
    d4h:          dict,
    btc_data:     dict,
    oi_matrix:    dict,
    direction:    str
) -> str:
    lines   = []
    d1_cls  = d1d.get("trend", {}).get("cls", "neutral")
    struct  = d1d.get("structure", {}).get("struct_bias", "neutral")

    if struct == d1_cls and struct != "neutral":
        lines.append(
            f"✔ Market structure {struct}ish — structure and trend aligned"
        )
    elif struct != "neutral":
        lines.append(
            f"⚠ Structure {struct}ish but trend {d1_cls} — partial alignment"
        )

    if sweep.get("confirmed"):
        lines.append(
            f"✔ Liquidity swept at {sweep.get('label', 'key level')} "
            f"— smart money stop hunt confirmed "
            f"({sweep.get('candles_ago', '?')} candles ago)"
        )
    elif sweep.get("detected"):
        lines.append(
            f"⚠ Sweep detected but not confirmed "
            f"at {sweep.get('label', 'key level')}"
        )

    if displacement.get("confirmed") and not displacement.get("moderate"):
        lines.append(
            f"✔ Strong displacement {displacement.get('type', '')}ish "
            f"— {displacement.get('range_mult', '?')}x ATR range, "
            f"vol {displacement.get('vol_spike', '?')}x"
        )
    elif displacement.get("moderate"):
        lines.append(
            f"⚠ Moderate displacement — {displacement.get('label', 'move detected')}"
        )

    if retest.get("confirmed"):
        lines.append(
            f"✔ Retest confirmed at {retest.get('zone_type', 'zone')} "
            f"— {retest.get('desc', '')}"
        )
    elif retest.get("status") == "partial":
        lines.append(
            f"⚠ Partial retest — {retest.get('desc', 'zone holding')}"
        )
    elif retest.get("status") == "pending":
        lines.append(
            f"⏳ Price in retest zone — waiting for rejection confirmation"
        )

    if btc_data:
        btc_cls = btc_data.get("trend", {}).get("cls", "neutral")
        if btc_cls == d1_cls:
            lines.append(f"✔ BTC {btc_cls}ish — confirms direction")
        elif btc_cls == "neutral":
            lines.append("⚠ BTC neutral — no conflict")
        else:
            lines.append(f"⚠ BTC {btc_cls}ish — conflicts with {direction}")

    if oi_matrix:
        oi_label = oi_matrix.get("primary_label", "")
        if "confirm" in oi_label.lower():
            lines.append(f"✔ OI confirming — {oi_label}")
        elif oi_label:
            lines.append(f"⚠ OI unclear — {oi_label}")

    return "\n".join(lines) if lines else "No thesis available."


def build_risk_thesis(
    market:       dict,
    oi_matrix:    dict,
    btc_inst:     dict,
    retest:       dict,
    displacement: dict,
    d1d:          dict,
    session:      dict
) -> str:
    risks  = []
    d1_cls = d1d.get("trend", {}).get("cls", "neutral")

    fund = market.get("funding", 0) * 100
    if abs(fund) > 0.05:
        risks.append(f"⚠ Elevated funding {fund:.4f}% — squeeze risk present")
    elif abs(fund) > 0.03:
        risks.append(f"⚠ Funding {fund:.4f}% — monitor")

    if oi_matrix:
        oi_label = oi_matrix.get("primary_label", "")
        if "exhaust" in oi_label.lower():
            risks.append("⚠ OI exhaustion signal — momentum may be fading")
        crowding = oi_matrix.get("crowding_warning", "")
        if crowding:
            risks.append(f"⚠ {crowding}")

    for w in btc_inst.get("warnings", []):
        risks.append(f"⚠ {w}")

    if retest.get("status") in ("partial", "pending"):
        risks.append("⚠ Retest not fully confirmed — entry before ideal confirmation")

    if displacement.get("weak"):
        risks.append("⚠ Weak displacement — institutional conviction unclear")

    rsi = d1d.get("rsi")
    if rsi is not None:
        if rsi > 70 and d1_cls == "bull":
            risks.append(f"⚠ RSI {rsi:.1f} — elevated, exhaustion possible")
        elif rsi < 30 and d1_cls == "bear":
            risks.append(f"⚠ RSI {rsi:.1f} — oversold, bounce risk present")

    if session.get("score", 9) <= 2:
        risks.append(f"⚠ {session.get('name', 'Off hours')} — low volume session")

    return "\n".join(risks) if risks else "No significant risk factors identified."


def build_no_trade_explanation(
    no_trade: dict,
    regime:   dict,
    sweep:    dict,
    retest:   dict
) -> str:
    lines       = ["NO TRADE\n"]
    hard_blocks = no_trade.get("hard_blocks", [])
    soft_blocks = no_trade.get("soft_blocks", [])

    if hard_blocks:
        lines.append("Hard Blocks:")
        for b in hard_blocks:
            lines.append(f"  ✘ {b['reason']} — {b['detail']}")

    if soft_blocks:
        lines.append("\nWeaknesses:")
        for s in soft_blocks:
            lines.append(f"  ⚠ {s['reason']}")

    lines.append(f"\nRegime: {regime.get('label', '--')}")
    lines.append(f"Sweep:  {'Confirmed' if sweep.get('confirmed') else 'Not confirmed'}")
    lines.append(f"Retest: {retest.get('label', 'None')}")

    penalty = no_trade.get("score_penalty", 0)
    if penalty > 0:
        lines.append(f"\nScore penalty: -{penalty} pts from soft blocks")

    return "\n".join(lines)


def confidence_label(norm_score: float) -> str:
    if norm_score >= 85:
        return "Very High"
    if norm_score >= 68:
        return "High"
    if norm_score >= 52:
        return "Moderate"
    if norm_score >= 38:
        return "Low"
    return "Very Low"


def build_explanation(
    signal:       dict,
    sweep:        dict,
    displacement: dict,
    retest:       dict,
    d1d:          dict,
    d4h:          dict,
    btc_data:     dict,
    btc_inst:     dict,
    oi_matrix:    dict,
    market:       dict,
    regime:       dict,
    session:      dict,
    no_trade:     dict,
    wconf:        dict
) -> dict:
    direction    = signal.get("direction", "")
    score        = wconf.get("norm_score", 0) if wconf else 0
    is_tradeable = direction in ("LONG", "SHORT")

    if is_tradeable:
        thesis = build_trade_thesis(
            sweep        = sweep,
            displacement = displacement,
            retest       = retest,
            d1d          = d1d,
            d4h          = d4h,
            btc_data     = btc_data,
            oi_matrix    = oi_matrix,
            direction    = direction,
        )
        risk_thesis     = build_risk_thesis(
            market       = market,
            oi_matrix    = oi_matrix,
            btc_inst     = btc_inst or {},
            retest       = retest,
            displacement = displacement,
            d1d          = d1d,
            session      = session,
        )
        no_trade_reason = ""
    else:
        thesis          = ""
        risk_thesis     = ""
        no_trade_reason = build_no_trade_explanation(
            no_trade = no_trade,
            regime   = regime,
            sweep    = sweep,
            retest   = retest,
        )

    return {
        "thesis":           thesis,
        "risk_thesis":      risk_thesis,
        "no_trade_reason":  no_trade_reason,
        "confidence":       score,
        "confidence_label": confidence_label(score),
        "direction":        direction,
        "grade":            signal.get("grade", "F"),
    }