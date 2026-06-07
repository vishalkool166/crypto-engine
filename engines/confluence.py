from config import cfg
from engines.orderblocks import detect_order_blocks


def score_confluence(
    d1w, d1d, d4h, d1h,
    market, key_levels,
    session, btc_data,
    btc_instability, regime,
    sweep, displacement,
    retest, oi_matrix,
    coin
) -> dict:

    factors = []
    total   = 0
    W       = cfg.WEIGHTS

    price    = market["price"]
    d1_price = d1d.get("price") or price

    def add(key, label, earned, max_w, passed, detail):
        nonlocal total
        e = min(earned, max_w)
        factors.append({
            "key":    key,
            "label":  label,
            "earned": e,
            "max":    max_w,
            "pass":   passed,
            "detail": detail
        })
        total += e

    # ── 1. Liquidity Sweep (12) ──
    sw_score = min(sweep.get("score", 0), W["liquidity_sweep"])
    add(
        "liquidity_sweep", "Liquidity Sweep",
        sw_score, W["liquidity_sweep"],
        sw_score >= 8,
        sweep.get("label", "No sweep") +
        " — Relevance: " +
        f"{sweep.get('relevance', {}).get('label', '--')}" +
        " · Intensity: " +
        f"{sweep.get('intensity', 0)}/10"
    )

    # ── 2. Retest Confirmation (12) ──
    rt_score   = min(retest.get("score", 0), W["retest_confirmation"])
    retest_dir = retest.get("trade_dir", "")
    d1_cls     = d1d["trend"]["cls"]

    opposing_retest = (
        (d1_cls == "bear" and retest_dir == "bull") or
        (d1_cls == "bull" and retest_dir == "bear")
    )

    retest_detail = retest.get("label", "") + " — " + retest.get("desc", "")

    if opposing_retest and retest.get("score", 0) > 0:
        retest_detail = (
            retest.get("label", "") + " — " +
            retest.get("desc", "") +
            " · Retracement into " +
            ("supply" if d1_cls == "bear" else "demand")
        )

    add(
        "retest_confirmation", "Retest Confirmation",
        rt_score, W["retest_confirmation"],
        rt_score >= 9,
        retest_detail
    )

    # ── 3. Displacement (11) ──
    dp_score = min(displacement.get("score", 0), W["displacement"])
    add(
        "displacement", "Displacement",
        dp_score, W["displacement"],
        dp_score >= 8,
        displacement.get("label", "None") + " — " + displacement.get("desc", "")
    )

    # ── 4. Market Regime (10) ──
    add(
        "market_regime", "Market Regime",
        W["market_regime"] if regime["tradeable"] else 0,
        W["market_regime"],
        regime["tradeable"],
        regime["label"] + " — " + regime["desc"]
    )

    # ── 5. Weekly Filter (10) ──
    wk_cls    = d1w["trend"]["cls"]
    d1_cls    = d1d["trend"]["cls"]
    wk_aligned = (
        (wk_cls == "bull" and d1_cls == "bull") or
        (wk_cls == "bear" and d1_cls == "bear")
    )
    wk_neutral = wk_cls == "neutral"

    # Weekly ema200 missing reduces confidence —
    # fewer data points means less reliable trend read
    wk_ema200_missing = d1w.get("ema200") is None
    wk_score = (
        W["weekly_filter"] if wk_aligned else
        round(W["weekly_filter"] * 0.5) if wk_neutral else 0
    )
    if wk_ema200_missing and wk_score > 0:
        wk_score = round(wk_score * 0.8)

    wk_detail = (
        "Weekly aligned" if wk_aligned else
        "Weekly neutral" if wk_neutral else
        "Weekly conflicts"
    )
    if wk_ema200_missing:
        wk_detail += " (EMA200 unavailable — reduced confidence)"

    add(
        "weekly_filter", "Weekly Filter",
        wk_score, W["weekly_filter"],
        wk_score >= 7,
        wk_detail
    )

    # ── 6. Market Structure (9) ──
    sb         = d1d["structure"]["struct_bias"]
    st_aligned = (
        (sb == "bull" and d1_cls == "bull") or
        (sb == "bear" and d1_cls == "bear")
    )
    st_score = (
        W["market_structure"] if st_aligned else
        4 if sb != "neutral" else 0
    )
    add(
        "market_structure", "Market Structure",
        st_score, W["market_structure"],
        st_score >= 7,
        f"Structure: {sb}"
    )

    # ── 7. Session Timing (8) ──
    ss_score = round((session["score"] / 9) * W["session_timing"])
    add(
        "session_timing", "Session Timing",
        ss_score, W["session_timing"],
        ss_score >= 5,
        f"{session['name']} — {session['quality']}"
    )

    # ── 8. BTC Alignment (8) ──
    btc_score  = 0
    btc_detail = ""

    if coin == "BTC":
        btc_score = (
            W["btc_alignment"]
            if btc_instability["stable"]
            else max(0, W["btc_alignment"] - len(btc_instability["warnings"]) * 2)
        )
        btc_detail = (
            "BTC is base asset — stable"
            if btc_instability["stable"]
            else btc_instability["warnings"][0]
        )
    elif btc_data:
        btc_cls = btc_data["trend"]["cls"]
        ba      = (
            (d1_cls == "bull" and btc_cls == "bull") or
            (d1_cls == "bear" and btc_cls == "bear")
        )
        bn      = btc_cls == "neutral"
        penalty = len(btc_instability.get("warnings", [])) * 2
        btc_score = (
            max(0, W["btc_alignment"] - penalty) if ba else
            max(0, 4 - penalty) if bn else 0
        )
        btc_detail = (
            f"BTC {btc_cls} — confirms" if ba else
            "BTC neutral" if bn else
            f"BTC {btc_cls} — conflicts"
        )

    add(
        "btc_alignment", "BTC Alignment",
        btc_score, W["btc_alignment"],
        btc_score >= 6,
        btc_detail
    )

    # ── 9. OI Behavior (7) ──
    oi_score = min(oi_matrix.get("primary_score", 0), W["oi_behavior"])
    add(
        "oi_behavior", "OI Behavior",
        oi_score, W["oi_behavior"],
        oi_score >= 5,
        oi_matrix.get("primary_label", "OI unclear")
    )

    # ── 10. Volume Expansion (7) ──
    # Use best of 4H or daily — daily catches big moves
    # that 4H alone misses
    vr_4h = (
        d4h["cur_vol"] / d4h["vol_ma5"]
        if d4h.get("vol_ma5") and d4h["vol_ma5"] > 0 else 0
    )
    vr_1d = (
        d1d["cur_vol"] / d1d["vol_ma5"]
        if d1d.get("vol_ma5") and d1d["vol_ma5"] > 0 else 0
    )
    vr      = max(vr_4h, vr_1d)
    v_score = (
        W["volume_expansion"] if vr > 1.5 else
        4 if vr > 0.85 else 0
    )
    add(
        "volume_expansion", "Volume Expansion",
        v_score, W["volume_expansion"],
        v_score >= 5,
        f"4H vol {vr_4h*100:.0f}% of MA5 · 1D vol {vr_1d*100:.0f}% of MA5"
    )

    # ── 11. Funding Rate (6) ──
    add(
        "funding_extreme", "Funding Rate",
        min(oi_matrix.get("funding_score", 6), W["funding_extreme"]),
        W["funding_extreme"],
        oi_matrix.get("funding_score", 6) >= 4,
        oi_matrix.get("funding_warning") or
        f"Funding {market['funding']*100:.4f}% — neutral"
    )

    # ── 12. RSI Divergence (4) ──
    # Divergence is more predictive than raw RSI values
    div      = d4h.get("divergence", {})
    div_type = div.get("type", "none")
    div_ok   = (
        (div_type in ["bullish", "hidden-bull"] and d1_cls == "bull") or
        (div_type in ["bearish", "hidden-bear"] and d1_cls == "bear")
    )
    add(
        "rsi_divergence", "RSI Divergence",
        W["rsi_divergence"] if div_ok else 0,
        W["rsi_divergence"],
        div_ok,
        f"4H: {div.get('label', 'None')}"
    )

    # ── 13. ATR Volatility (3) ──
    # ATR divided by d1d price — both from same timeframe
    atr    = d1d.get("atr") or 0
    ap     = (atr / d1_price * 100) if d1_price > 0 else 0
    atr_ok = 0.5 < ap < 5
    add(
        "atr_volatility", "ATR Volatility",
        W["atr_volatility"] if atr_ok else 1,
        W["atr_volatility"],
        atr_ok,
        f"ATR {ap:.2f}% of price"
    )

    # ── 14. RSI Context (2) ──
    # Raw RSI contributes to score only — never blocks
    rsi    = d1d.get("rsi")
    rsi_ok = (
        rsi is not None and (
            (d1_cls == "bull" and 40 < rsi < 75) or
            (d1_cls == "bear" and 25 < rsi < 60)
        )
    )
    add(
        "rsi_context", "RSI Context",
        W["rsi_context"] if rsi_ok else 0,
        W["rsi_context"],
        rsi_ok,
        f"Daily RSI {rsi:.1f}" if rsi else "RSI N/A"
    )

    # ── 15. MACD Histogram (1) ──
    macd    = d4h.get("macd")
    macd_ok = (
        macd is not None and (
            (d4h["trend"]["cls"] == "bull" and macd["bullish"] and macd["expanding"]) or
            (d4h["trend"]["cls"] == "bear" and macd["bearish"] and macd["expanding"])
        )
    )
    add(
        "macd_histogram", "MACD Histogram",
        W["macd_histogram"] if macd_ok else 0,
        W["macd_histogram"],
        macd_ok,
        (
            f"Hist {'positive' if macd['bullish'] else 'negative'}, "
            f"{'expanding' if macd['expanding'] else 'contracting'}"
        ) if macd else "N/A"
    )

    # ── 16. Order Blocks (4) ──
    ob_score  = 0
    ob_label  = "No OB detected"
    ob_detail = "No order blocks found"

    try:
        fvgs   = d4h.get("fvgs", [])
        d4_cls = d4h["trend"]["cls"]

        for fvg in fvgs:
            fvg_mid  = fvg.get("mid", 0)
            if not fvg_mid:
                continue
            dist_pct = abs(price - fvg_mid) / price * 100

            if fvg["type"] == "bull" and d4_cls == "bull":
                if dist_pct < 1.0:
                    ob_score  = 8
                    ob_label  = "✅ In Bull OB Zone"
                    ob_detail = f"Bull FVG/OB @ {fvg['bottom']:.4f}-{fvg['top']:.4f}"
                    break
                elif dist_pct < 2.5:
                    ob_score  = 5
                    ob_label  = "⚡ Near Bull OB"
                    ob_detail = f"Approaching Bull OB @ {fvg_mid:.4f}"

            elif fvg["type"] == "bear" and d4_cls == "bear":
                if dist_pct < 1.0:
                    ob_score  = 8
                    ob_label  = "✅ In Bear OB Zone"
                    ob_detail = f"Bear FVG/OB @ {fvg['bottom']:.4f}-{fvg['top']:.4f}"
                    break
                elif dist_pct < 2.5:
                    ob_score  = 5
                    ob_label  = "⚡ Near Bear OB"
                    ob_detail = f"Approaching Bear OB @ {fvg_mid:.4f}"

        if ob_score == 0:
            d1_fvgs = d1d.get("fvgs", [])
            d1_cls2 = d1d["trend"]["cls"]
            for fvg in d1_fvgs:
                fvg_mid  = fvg.get("mid", 0)
                if not fvg_mid:
                    continue
                dist_pct = abs(price - fvg_mid) / price * 100
                if fvg["type"] == "bull" and d1_cls2 == "bull" and dist_pct < 2.0:
                    ob_score  = 4
                    ob_label  = "📍 1D Bull OB nearby"
                    ob_detail = f"Daily Bull OB @ {fvg_mid:.4f}"
                    break
                elif fvg["type"] == "bear" and d1_cls2 == "bear" and dist_pct < 2.0:
                    ob_score  = 4
                    ob_label  = "📍 1D Bear OB nearby"
                    ob_detail = f"Daily Bear OB @ {fvg_mid:.4f}"
                    break

    except Exception as e:
        ob_score  = 0
        ob_label  = "OB detection error"
        ob_detail = str(e)

    ob_max = W.get("order_blocks", 4)
    add(
        "order_blocks", "Order Blocks",
        min(ob_score, ob_max), ob_max,
        ob_score >= 5,
        f"{ob_label} — {ob_detail}"
    )

    max_weight = cfg.MAX_WEIGHT
    norm_score = round((total / max_weight) * 100)

    return {
        "factors":      factors,
        "total_earned": total,
        "max_possible": max_weight,
        "norm_score":   norm_score
    }