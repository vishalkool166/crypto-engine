from config import cfg

MARKET_QUALITY_KEYS = [
    "market_regime",
    "weekly_filter",
    "market_structure",
    "btc_alignment",
    "atr_volatility",
    "rsi_context",
    "funding_extreme",
    "oi_behavior",
    "volume_expansion",
]

ENTRY_OPPORTUNITY_KEYS = [
    "liquidity_sweep",
    "retest_confirmation",
    "displacement",
    "session_timing",
    "rsi_divergence",
    "macd_histogram",
    "order_blocks",
]

NON_NEGOTIABLE_KEYS = [
    "market_regime",
    "weekly_filter",
]


def _get_btc_correlation(coin: str) -> float:
    try:
        from database import SessionLocal, CoinConfig
        with SessionLocal() as db:
            row = db.query(CoinConfig).filter(CoinConfig.coin == coin).first()
            if row and row.btc_correlation is not None:
                return float(row.btc_correlation)
    except Exception:
        pass
    return 0.8


def score_confluence(
    d1w, d1d, d4h, d1h,
    market, key_levels,
    session, btc_data,
    btc_instability, regime,
    sweep, displacement,
    retest, oi_matrix,
    coin,
    btc_4h: dict = None
) -> dict:

    factors = []
    total   = 0
    W       = cfg.WEIGHTS

    price    = market["price"]
    d1_price = d1d.get("price") or price
    d1_cls   = d1d["trend"]["cls"]
    d4_cls   = d4h["trend"]["cls"]

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

    sw_score = min(sweep.get("score", 0), W["liquidity_sweep"])
    add(
        "liquidity_sweep", "Liquidity Sweep",
        sw_score, W["liquidity_sweep"],
        sw_score >= 8,
        sweep.get("label", "No sweep") +
        " — Age: " + sweep.get("relevance", {}).get("label", "--") +
        " · " + sweep.get("desc", "")
    )

    rt_score   = min(retest.get("score", 0), W["retest_confirmation"])
    retest_dir = retest.get("trade_dir", "")

    opposing_retest = (
        (d1_cls == "bear" and retest_dir == "bull") or
        (d1_cls == "bull" and retest_dir == "bear")
    )

    retest_detail = retest.get("label", "") + " — " + retest.get("desc", "")
    if opposing_retest and retest.get("score", 0) > 0:
        retest_detail = (
            retest.get("label", "") + " — " + retest.get("desc", "") +
            " · Retracement into " + ("supply" if d1_cls == "bear" else "demand")
        )

    add(
        "retest_confirmation", "Retest Confirmation",
        rt_score, W["retest_confirmation"],
        rt_score >= 9,
        retest_detail
    )

    dp_score = min(displacement.get("score", 0), W["displacement"])
    add(
        "displacement", "Displacement",
        dp_score, W["displacement"],
        dp_score >= 8,
        displacement.get("label", "None") + " — " + displacement.get("desc", "")
    )

    add(
        "market_regime", "Market Regime",
        W["market_regime"] if regime["tradeable"] else 0,
        W["market_regime"],
        regime["tradeable"],
        regime["label"] + " — " + regime["desc"]
    )

    wk_cls     = d1w["trend"]["cls"]
    wk_aligned = (
        (wk_cls == "bull" and d1_cls == "bull") or
        (wk_cls == "bear" and d1_cls == "bear")
    )
    wk_neutral        = wk_cls == "neutral"
    wk_ema200_missing = d1w.get("ema200") is None

    wk_score = (
        W["weekly_filter"] if wk_aligned else
        round(W["weekly_filter"] * 0.4) if wk_neutral else
        0
    )
    if wk_ema200_missing and wk_score > 0:
        wk_score = round(wk_score * 0.8)

    wk_detail = (
        "Weekly aligned" if wk_aligned else
        "Weekly neutral — reduced score" if wk_neutral else
        "Weekly conflicts — blocked"
    )
    if wk_ema200_missing:
        wk_detail += " (EMA200 unavailable)"

    add(
        "weekly_filter", "Weekly Filter",
        wk_score, W["weekly_filter"],
        wk_score >= 7,
        wk_detail
    )

    sb         = d1d["structure"]["struct_bias"]
    st_aligned = (
        (sb == "bull" and d1_cls == "bull") or
        (sb == "bear" and d1_cls == "bear")
    )
    st_score = (
        W["market_structure"] if st_aligned else
        3 if sb != "neutral" else 0
    )
    add(
        "market_structure", "Market Structure",
        st_score, W["market_structure"],
        st_score >= 7,
        f"Structure: {sb}"
    )

    ss_score = round((session["score"] / 9) * W["session_timing"])
    add(
        "session_timing", "Session Timing",
        ss_score, W["session_timing"],
        ss_score >= 5,
        f"{session['name']} — {session['quality']}"
    )

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
        btc_1d_cls = btc_data["trend"]["cls"]
        btc_4h_cls = btc_4h["trend"]["cls"] if btc_4h else None

        if btc_4h_cls:
            both_bull = btc_1d_cls == "bull" and btc_4h_cls == "bull"
            both_bear = btc_1d_cls == "bear" and btc_4h_cls == "bear"
            conflict  = (
                (btc_1d_cls == "bull" and btc_4h_cls == "bear") or
                (btc_1d_cls == "bear" and btc_4h_cls == "bull")
            )

            if both_bull or both_bear:
                btc_aligned_cls = btc_1d_cls
                alignment_mult  = 1.0
                align_note      = f"BTC 1D+4H both {btc_1d_cls}"
            elif conflict:
                btc_aligned_cls = btc_1d_cls
                alignment_mult  = 0.4
                align_note      = f"BTC 1D {btc_1d_cls} but 4H {btc_4h_cls} — conflict"
            else:
                btc_aligned_cls = btc_1d_cls
                alignment_mult  = 0.7
                align_note      = f"BTC 1D {btc_1d_cls}, 4H neutral"
        else:
            btc_aligned_cls = btc_1d_cls
            alignment_mult  = 1.0
            align_note      = f"BTC {btc_1d_cls}"

        ba      = (
            (d1_cls == "bull" and btc_aligned_cls == "bull") or
            (d1_cls == "bear" and btc_aligned_cls == "bear")
        )
        bn      = btc_aligned_cls == "neutral"
        penalty = len(btc_instability.get("warnings", [])) * 2

        corr = _get_btc_correlation(coin)

        if ba:
            base_score = W["btc_alignment"]
            btc_detail = f"{align_note} — confirms direction"
        elif bn:
            base_score = round(W["btc_alignment"] * 0.4)
            btc_detail = "BTC neutral — partial score"
        else:
            base_score = round(W["btc_alignment"] * (1 - corr) * 0.5)
            btc_detail = f"{align_note} — conflicts (corr {corr:.1f})"

        btc_score = max(0, round(base_score * alignment_mult) - penalty)

    add(
        "btc_alignment", "BTC Alignment",
        btc_score, W["btc_alignment"],
        btc_score >= 6,
        btc_detail
    )

    oi_score = min(oi_matrix.get("primary_score", 0), W["oi_behavior"])
    add(
        "oi_behavior", "OI Behavior",
        oi_score, W["oi_behavior"],
        oi_score >= 5,
        oi_matrix.get("primary_label", "OI unclear")
    )

    vr_4h = (
        d4h["cur_vol"] / d4h["vol_ma5"]
        if d4h.get("vol_ma5") and d4h["vol_ma5"] > 0 else 0
    )
    vr_1d = (
        d1d["cur_vol"] / d1d["vol_ma5"]
        if d1d.get("vol_ma5") and d1d["vol_ma5"] > 0 else 0
    )

    v4h_score = (
        W["volume_expansion"] if vr_4h > 1.5 else
        round(W["volume_expansion"] * 0.6) if vr_4h > 0.85 else 0
    )
    v1d_score = (
        W["volume_expansion"] if vr_1d > 1.5 else
        round(W["volume_expansion"] * 0.6) if vr_1d > 0.85 else 0
    )
    v_score = round((v4h_score * 0.6) + (v1d_score * 0.4))

    add(
        "volume_expansion", "Volume Expansion",
        v_score, W["volume_expansion"],
        v_score >= 5,
        f"4H vol {vr_4h*100:.0f}% of MA · 1D vol {vr_1d*100:.0f}% of MA"
    )

    add(
        "funding_extreme", "Funding Rate",
        min(oi_matrix.get("funding_score", 6), W["funding_extreme"]),
        W["funding_extreme"],
        oi_matrix.get("funding_score", 6) >= 4,
        oi_matrix.get("funding_warning") or
        f"Funding {market['funding']*100:.4f}% — neutral"
    )

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

    atr    = d1d.get("atr") or 0
    ap     = (atr / d1_price * 100) if d1_price > 0 else 0
    atr_ok = 0.5 < ap < 6
    add(
        "atr_volatility", "ATR Volatility",
        W["atr_volatility"] if atr_ok else 1,
        W["atr_volatility"],
        atr_ok,
        f"ATR {ap:.2f}% of price"
    )

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

    macd    = d4h.get("macd")
    macd_ok = (
        macd is not None and (
            (d4_cls == "bull" and macd["bullish"] and macd["exhausting"]) or
            (d4_cls == "bear" and macd["bearish"] and macd["exhausting"])
        )
    )
    add(
        "macd_histogram", "MACD Histogram",
        W["macd_histogram"] if macd_ok else 0,
        W["macd_histogram"],
        macd_ok,
        (
            f"Hist {'positive' if macd['bullish'] else 'negative'}, "
            f"{'expanding' if macd['exhausting'] else 'active'}"
        ) if macd else "N/A"
    )

    ob_max    = W.get("order_blocks", 4)
    ob_score  = 0
    ob_label  = "No OB detected"
    ob_detail = ""

    ob_4h = d4h.get("order_blocks", {})
    ob_1d = d1d.get("order_blocks", {})

    nearest_4h = (
        ob_4h.get("nearest_bull") if d4_cls == "bull"
        else ob_4h.get("nearest_bear")
    )

    if nearest_4h:
        if nearest_4h["in_zone"]:
            ob_score  = ob_max
            ob_label  = ob_4h.get("label", "In 4H OB Zone")
            ob_detail = ob_4h.get("desc", "")
        elif nearest_4h["approaching"]:
            ob_score  = round(ob_max * 0.6)
            ob_label  = "Approaching 4H OB"
            ob_detail = ob_4h.get("desc", "")

    for b in ob_4h.get("breakers", []):
        if b.get("in_zone") or b.get("approaching"):
            ob_score  = ob_max
            ob_label  = "Breaker Block Active"
            ob_detail = b.get("desc", "")
            break

    if ob_score == 0:
        nearest_1d = (
            ob_1d.get("nearest_bull") if d1_cls == "bull"
            else ob_1d.get("nearest_bear")
        )
        if nearest_1d and (nearest_1d["in_zone"] or nearest_1d["approaching"]):
            ob_score  = round(ob_max * 0.5)
            ob_label  = "1D OB nearby"
            ob_detail = ob_1d.get("desc", "")

    add(
        "order_blocks", "Order Blocks",
        min(ob_score, ob_max), ob_max,
        ob_score >= round(ob_max * 0.6),
        f"{ob_label} — {ob_detail}" if ob_detail else ob_label
    )

    max_weight = cfg.MAX_WEIGHT
    norm_score = round((total / max_weight) * 100)

    market_earned = sum(
        f["earned"] for f in factors
        if f["key"] in MARKET_QUALITY_KEYS
    )
    market_max = sum(
        W[k] for k in MARKET_QUALITY_KEYS
        if k in W
    )
    market_score = round(
        (market_earned / market_max) * 100
    ) if market_max > 0 else 0

    entry_earned = sum(
        f["earned"] for f in factors
        if f["key"] in ENTRY_OPPORTUNITY_KEYS
    )
    entry_max = sum(
        W[k] for k in ENTRY_OPPORTUNITY_KEYS
        if k in W
    )
    entry_score = round(
        (entry_earned / entry_max) * 100
    ) if entry_max > 0 else 0

    btc_factor    = next((f for f in factors if f["key"] == "btc_alignment"), None)
    btc_score_val = btc_factor["earned"] if btc_factor else 0

    non_neg_passed = all(
        next((f["pass"] for f in factors if f["key"] == k), False)
        for k in NON_NEGOTIABLE_KEYS
    )
    non_neg_failed = [
        k for k in NON_NEGOTIABLE_KEYS
        if not next((f["pass"] for f in factors if f["key"] == k), False)
    ]

    return {
        "factors":        factors,
        "total_earned":   total,
        "max_possible":   max_weight,
        "norm_score":     norm_score,
        "market_score":   market_score,
        "entry_score":    entry_score,
        "market_earned":  market_earned,
        "market_max":     market_max,
        "entry_earned":   entry_earned,
        "entry_max":      entry_max,
        "btc_score":      btc_score_val,
        "non_neg_passed": non_neg_passed,
        "non_neg_failed": non_neg_failed,
    }