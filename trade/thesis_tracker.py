import json
import logging
import time
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger(__name__)

VELOCITY_STALL_HOURS  = 2.0
VELOCITY_HEALTHY_RATIO = 0.05

GRADE_TIME_LIMITS = {
    "A+": 48.0,
    "A":  32.0,
    "B":  16.0,
}

THESIS_THRESHOLDS = {
    "hold":         0.80,
    "monitor":      0.60,
    "tighten":      0.40,
    "prepare_exit": 0.20,
    "exit":         0.00,
}

_active_theses: dict = {}


def _get_pillar_weights() -> dict:
    try:
        from ml.pillar_analyzer import get_current_weights
        return get_current_weights()
    except Exception:
        return {
            "sweep":         0.25,
            "zone":          0.25,
            "structure":     0.20,
            "btc_alignment": 0.15,
            "regime":        0.15,
        }


@dataclass
class PillarState:
    name:   str
    valid:  bool
    score:  float
    weight: float
    reason: str = ""

    @property
    def weighted_score(self) -> float:
        return self.score * self.weight if self.valid else 0.0


@dataclass
class ThesisState:
    trade_id:              int
    coin:                  str
    direction:             str
    grade:                 str
    entry_price:           float
    sl_price:              float
    tp1_price:             float
    tp2_price:             Optional[float]
    entry_regime:          str
    entry_session:         str
    entry_thesis_strength: float = 1.0
    expected_move_pct:     float = 0.0

    pillars:               dict  = field(default_factory=dict)
    thesis_strength:       float = 1.0
    action:                str   = "hold"
    action_reason:         str   = ""

    hours_open:            float = 0.0
    live_price:            float = 0.0
    move_pct:              float = 0.0
    captured_move_pct:     float = 0.0
    velocity:              float = 0.0
    velocity_stalled:      bool  = False
    stall_hours:           float = 0.0

    last_evaluated:        float = field(default_factory=time.time)
    snapshots:             list  = field(default_factory=list)


def create_thesis(
    trade_id:    int,
    coin:        str,
    direction:   str,
    grade:       str,
    entry_price: float,
    sl_price:    float,
    tp1_price:   float,
    tp2_price:   Optional[float],
    regime:      str,
    session:     str,
    signal_data: dict,
) -> ThesisState:
    is_long = direction == "LONG"

    target = tp2_price if tp2_price else tp1_price
    if entry_price > 0 and target:
        if is_long:
            expected_move_pct = (target - entry_price) / entry_price * 100
        else:
            expected_move_pct = (entry_price - target) / entry_price * 100
    else:
        expected_move_pct = 0.0

    weights = _get_pillar_weights()

    sweep_score   = float(signal_data.get("sweep_score",   0) or 0)
    zone_score    = float(signal_data.get("zone_score",    0) or 0)
    trigger_score = float(signal_data.get("trigger_score", 0) or 0)

    pillars = {
        "sweep": PillarState(
            name   = "sweep",
            valid  = sweep_score >= 0.30,
            score  = sweep_score,
            weight = weights["sweep"],
            reason = f"Sweep score {sweep_score:.2f} at entry",
        ),
        "zone": PillarState(
            name   = "zone",
            valid  = zone_score >= 0.40,
            score  = zone_score,
            weight = weights["zone"],
            reason = f"Zone score {zone_score:.2f} at entry",
        ),
        "structure": PillarState(
            name   = "structure",
            valid  = True,
            score  = trigger_score,
            weight = weights["structure"],
            reason = "Structure intact at entry",
        ),
        "btc_alignment": PillarState(
            name   = "btc_alignment",
            valid  = True,
            score  = 0.75,
            weight = weights["btc_alignment"],
            reason = "BTC aligned at entry",
        ),
        "regime": PillarState(
            name   = "regime",
            valid  = True,
            score  = 0.80,
            weight = weights["regime"],
            reason = f"Regime {regime} at entry",
        ),
    }

    thesis = ThesisState(
        trade_id              = trade_id,
        coin                  = coin,
        direction             = direction,
        grade                 = grade,
        entry_price           = entry_price,
        sl_price              = sl_price,
        tp1_price             = tp1_price,
        tp2_price             = tp2_price,
        entry_regime          = regime,
        entry_session         = session,
        entry_thesis_strength = 1.0,
        expected_move_pct     = round(expected_move_pct, 4),
        pillars               = pillars,
        thesis_strength       = 1.0,
        action                = "hold",
    )

    _active_theses[trade_id] = thesis
    log.info(
        "Thesis created: trade_id=%s %s %s grade:%s expected_move:%.2f%%",
        trade_id, coin, direction, grade, expected_move_pct
    )
    return thesis


def get_thesis(trade_id: int) -> Optional[ThesisState]:
    return _active_theses.get(trade_id)


def remove_thesis(trade_id: int) -> None:
    _active_theses.pop(trade_id, None)


def get_all_active() -> dict:
    return dict(_active_theses)


async def evaluate(trade_id: int, trade: dict) -> Optional[ThesisState]:
    thesis = _active_theses.get(trade_id)
    if not thesis:
        return None

    try:
        coin    = thesis.coin
        entry   = thesis.entry_price
        is_long = thesis.direction == "LONG"

        from trade.ws import get_mark_price
        live_price = get_mark_price(coin) or entry
        thesis.live_price = live_price

        from database import SessionLocal, Trade as TradeModel
        with SessionLocal() as db:
            t = db.query(TradeModel).filter(TradeModel.id == trade_id).first()
            if not t or not t.is_active:
                remove_thesis(trade_id)
                return None
            opened_at = t.opened_at
            if opened_at.tzinfo is None:
                opened_at = opened_at.replace(tzinfo=timezone.utc)

        hours_open = (datetime.now(timezone.utc) - opened_at).total_seconds() / 3600
        thesis.hours_open = round(hours_open, 2)

        if entry > 0:
            move_pct = (
                (live_price - entry) / entry * 100 if is_long
                else (entry - live_price) / entry * 100
            )
        else:
            move_pct = 0.0
        thesis.move_pct = round(move_pct, 4)

        if thesis.expected_move_pct > 0:
            thesis.captured_move_pct = round(
                max(0.0, move_pct / thesis.expected_move_pct * 100), 2
            )
        else:
            thesis.captured_move_pct = 0.0

        _update_velocity(thesis, move_pct, hours_open)

        weights = _get_pillar_weights()
        for pillar in thesis.pillars.values():
            pillar.weight = weights.get(pillar.name, pillar.weight)

        await _evaluate_sweep_pillar(thesis, live_price)
        await _evaluate_zone_pillar(thesis, live_price)
        await _evaluate_structure_pillar(thesis)
        await _evaluate_btc_pillar(thesis)
        await _evaluate_regime_pillar(thesis)

        total_weight = sum(p.weight for p in thesis.pillars.values())
        weighted_sum = sum(p.weighted_score for p in thesis.pillars.values())
        thesis.thesis_strength = round(
            weighted_sum / total_weight if total_weight > 0 else 0.0, 3
        )

        thesis.action, thesis.action_reason = _determine_action(thesis)

        _save_snapshot(thesis)

        thesis.last_evaluated = time.time()

        log.debug(
            "Thesis evaluated: %s strength:%.2f action:%s move:%.2f%% captured:%.1f%%",
            coin, thesis.thesis_strength, thesis.action,
            move_pct, thesis.captured_move_pct
        )

        return thesis

    except Exception as e:
        log.error("evaluate thesis trade_id=%s: %s", trade_id, e)
        return thesis


def _update_velocity(thesis: ThesisState, current_move_pct: float, hours_open: float) -> None:
    snapshots = thesis.snapshots
    if not snapshots:
        thesis.velocity       = 0.0
        thesis.stall_hours    = 0.0
        thesis.velocity_stalled = False
        return

    one_hour_ago = time.time() - 3600
    recent = [s for s in snapshots if s.get("ts", 0) >= one_hour_ago]

    if recent:
        oldest_move = recent[0].get("move_pct", 0)
    else:
        oldest_move = snapshots[-1].get("move_pct", 0) if snapshots else 0

    velocity       = current_move_pct - oldest_move
    thesis.velocity = round(velocity, 4)

    if thesis.expected_move_pct > 0:
        min_healthy = thesis.expected_move_pct * VELOCITY_HEALTHY_RATIO
    else:
        min_healthy = 0.1

    if velocity < min_healthy and current_move_pct > 0:
        thesis.stall_hours = round(thesis.stall_hours + 0.5, 1)
    elif velocity <= 0 and current_move_pct <= 0:
        thesis.stall_hours = 0.0
    else:
        thesis.stall_hours = 0.0

    thesis.velocity_stalled = thesis.stall_hours >= VELOCITY_STALL_HOURS


async def _evaluate_sweep_pillar(thesis: ThesisState, live_price: float) -> None:
    pillar  = thesis.pillars["sweep"]
    is_long = thesis.direction == "LONG"

    try:
        from data.store import load_candles
        from engines.indicators import calculate_all

        df_1h = load_candles(thesis.coin, "1h", limit=50)
        if df_1h is None or len(df_1h) < 10:
            return

        d1h    = calculate_all(df_1h, timeframe="1h")
        swings = d1h.get("swings", {})

        if is_long:
            last_low = swings.get("last_low", {})
            if last_low:
                sweep_level = float(last_low.get("price", 0))
                if sweep_level > 0 and live_price < sweep_level * 0.998:
                    pillar.valid  = False
                    pillar.score  = 0.0
                    pillar.reason = f"Price {live_price:.4f} broke below sweep level {sweep_level:.4f}"
                    return
        else:
            last_high = swings.get("last_high", {})
            if last_high:
                sweep_level = float(last_high.get("price", 0))
                if sweep_level > 0 and live_price > sweep_level * 1.002:
                    pillar.valid  = False
                    pillar.score  = 0.0
                    pillar.reason = f"Price {live_price:.4f} broke above sweep level {sweep_level:.4f}"
                    return

        if not pillar.valid:
            pillar.valid  = True
            pillar.score  = max(0.3, pillar.score)
            pillar.reason = "Sweep level recovered"

    except Exception as e:
        log.debug("_evaluate_sweep_pillar %s: %s", thesis.coin, e)


async def _evaluate_zone_pillar(thesis: ThesisState, live_price: float) -> None:
    pillar  = thesis.pillars["zone"]
    is_long = thesis.direction == "LONG"

    try:
        from data.cache import cache
        cached = cache.get_raw(f"signal_{thesis.coin}")
        if not cached:
            return

        zone = cached.get("zone", {})
        if not zone or not zone.get("top") or not zone.get("bottom"):
            return

        zone_top    = float(zone.get("top",    0))
        zone_bottom = float(zone.get("bottom", 0))

        if is_long:
            if live_price < zone_bottom * 0.997:
                pillar.valid  = False
                pillar.score  = 0.0
                pillar.reason = f"Price {live_price:.4f} closed below demand zone {zone_bottom:.4f}"
            else:
                if not pillar.valid:
                    pillar.valid  = True
                    pillar.score  = max(0.3, pillar.score)
                    pillar.reason = "Zone holding"
        else:
            if live_price > zone_top * 1.003:
                pillar.valid  = False
                pillar.score  = 0.0
                pillar.reason = f"Price {live_price:.4f} closed above supply zone {zone_top:.4f}"
            else:
                if not pillar.valid:
                    pillar.valid  = True
                    pillar.score  = max(0.3, pillar.score)
                    pillar.reason = "Zone holding"

    except Exception as e:
        log.debug("_evaluate_zone_pillar %s: %s", thesis.coin, e)


async def _evaluate_structure_pillar(thesis: ThesisState) -> None:
    pillar  = thesis.pillars["structure"]
    is_long = thesis.direction == "LONG"

    try:
        from data.store import load_candles
        from engines.indicators import calculate_all

        df_4h = load_candles(thesis.coin, "4h", limit=100)
        if df_4h is None or len(df_4h) < 20:
            return

        d4h    = calculate_all(df_4h, timeframe="4h")
        events = d4h.get("structure", {}).get("events", [])

        for event in events:
            event_type = event.get("type", "")
            event_bias = event.get("bias", "")

            if event_type == "BOS":
                if is_long and event_bias == "bear":
                    pillar.valid  = False
                    pillar.score  = 0.0
                    pillar.reason = f"Bearish BOS — {event.get('desc', 'swing low broken')}"
                    return
                elif not is_long and event_bias == "bull":
                    pillar.valid  = False
                    pillar.score  = 0.0
                    pillar.reason = f"Bullish BOS — {event.get('desc', 'swing high broken')}"
                    return

            elif event_type == "CHoCH":
                if is_long and event_bias == "bear":
                    pillar.score  = max(0.2, pillar.score * 0.6)
                    pillar.reason = "Bearish CHoCH detected — potential reversal"
                elif not is_long and event_bias == "bull":
                    pillar.score  = max(0.2, pillar.score * 0.6)
                    pillar.reason = "Bullish CHoCH detected — potential reversal"

        if pillar.valid and "BOS" not in pillar.reason:
            pillar.score  = min(1.0, pillar.score + 0.05)
            pillar.reason = "Structure intact"

    except Exception as e:
        log.debug("_evaluate_structure_pillar %s: %s", thesis.coin, e)


async def _evaluate_btc_pillar(thesis: ThesisState) -> None:
    pillar  = thesis.pillars["btc_alignment"]
    is_long = thesis.direction == "LONG"

    try:
        from data.cache import cache
        btc = cache.get_raw("btc_4h_data")
        if not btc:
            return

        btc_cls = btc.get("trend", {}).get("cls", "neutral")
        btc_adx = float(btc.get("adx") or 0)

        if is_long and btc_cls == "bear":
            if btc_adx >= 30:
                pillar.valid  = False
                pillar.score  = 0.0
                pillar.reason = f"BTC strongly bearish ADX:{btc_adx:.0f}"
            elif btc_adx >= 20:
                pillar.score  = max(0.2, pillar.score * 0.5)
                pillar.valid  = True
                pillar.reason = f"BTC bearish ADX:{btc_adx:.0f} — moderate headwind"
            else:
                pillar.score  = max(0.4, pillar.score * 0.8)
                pillar.valid  = True
                pillar.reason = f"BTC weakly bearish ADX:{btc_adx:.0f}"

        elif not is_long and btc_cls == "bull":
            if btc_adx >= 30:
                pillar.valid  = False
                pillar.score  = 0.0
                pillar.reason = f"BTC strongly bullish ADX:{btc_adx:.0f}"
            elif btc_adx >= 20:
                pillar.score  = max(0.2, pillar.score * 0.5)
                pillar.valid  = True
                pillar.reason = f"BTC bullish ADX:{btc_adx:.0f} — moderate headwind"
            else:
                pillar.score  = max(0.4, pillar.score * 0.8)
                pillar.valid  = True
                pillar.reason = f"BTC weakly bullish ADX:{btc_adx:.0f}"

        else:
            pillar.valid  = True
            pillar.score  = min(1.0, pillar.score + 0.02)
            pillar.reason = f"BTC {btc_cls} — aligned or neutral"

    except Exception as e:
        log.debug("_evaluate_btc_pillar %s: %s", thesis.coin, e)


async def _evaluate_regime_pillar(thesis: ThesisState) -> None:
    pillar  = thesis.pillars["regime"]
    is_long = thesis.direction == "LONG"

    try:
        from ml.regime_classifier import classify_current_regime
        current = classify_current_regime()
        regime  = current.get("regime", "unknown")

        adverse_long  = ["trending_bear"]
        adverse_short = ["trending_bull"]
        choppy        = ["choppy"]
        neutral       = ["ranging", "weak_trend", "unknown"]

        if is_long:
            if regime in adverse_long:
                pillar.valid  = False
                pillar.score  = 0.0
                pillar.reason = f"Regime {regime} — adverse for long"
            elif regime in choppy:
                pillar.score  = max(0.3, pillar.score * 0.6)
                pillar.valid  = True
                pillar.reason = f"Regime {regime} — choppy"
            elif regime in neutral:
                pillar.score  = max(0.5, pillar.score * 0.8)
                pillar.valid  = True
                pillar.reason = f"Regime {regime} — neutral"
            else:
                pillar.valid  = True
                pillar.score  = min(1.0, pillar.score + 0.05)
                pillar.reason = f"Regime {regime} — favorable"
        else:
            if regime in adverse_short:
                pillar.valid  = False
                pillar.score  = 0.0
                pillar.reason = f"Regime {regime} — adverse for short"
            elif regime in choppy:
                pillar.score  = max(0.3, pillar.score * 0.6)
                pillar.valid  = True
                pillar.reason = f"Regime {regime} — choppy"
            elif regime in neutral:
                pillar.score  = max(0.5, pillar.score * 0.8)
                pillar.valid  = True
                pillar.reason = f"Regime {regime} — neutral"
            else:
                pillar.valid  = True
                pillar.score  = min(1.0, pillar.score + 0.05)
                pillar.reason = f"Regime {regime} — favorable"

    except Exception as e:
        log.debug("_evaluate_regime_pillar %s: %s", thesis.coin, e)


def _determine_action(thesis: ThesisState) -> tuple[str, str]:
    strength      = thesis.thesis_strength
    hours_open    = thesis.hours_open
    move_pct      = thesis.move_pct
    grade         = thesis.grade
    stalled       = thesis.velocity_stalled
    stall_hours   = thesis.stall_hours
    captured      = thesis.captured_move_pct

    time_limit    = GRADE_TIME_LIMITS.get(grade, 32.0)
    time_used_pct = hours_open / time_limit if time_limit > 0 else 1.0

    if hours_open >= time_limit:
        if move_pct > 0.1:
            return "exit", f"Time limit {time_limit}h reached — closing profitable"
        elif move_pct > -0.1:
            return "exit", f"Time limit {time_limit}h reached — breakeven"
        else:
            return "exit", f"Time limit {time_limit}h reached — adverse"

    if strength < 0.20:
        return "exit", f"Thesis {strength:.2f} — all pillars failed"

    if strength < 0.40:
        if move_pct > 0.5:
            return "exit", f"Thesis {strength:.2f} — degraded, protecting meaningful profit"
        return "prepare_exit", f"Thesis {strength:.2f} — severely degraded"

    if stalled and stall_hours >= VELOCITY_STALL_HOURS:
        if captured >= 60:
            return "exit", f"Velocity stalled {stall_hours:.1f}h — captured {captured:.0f}%"
        elif captured >= 30 and move_pct > 0:
            return "tighten", f"Velocity stalled {stall_hours:.1f}h — tightening"
        elif move_pct <= 0:
            return "tighten", f"Velocity stalled {stall_hours:.1f}h — adverse"

    if strength < 0.60:
        return "tighten", f"Thesis {strength:.2f} — tighten SL"

    if strength < 0.80:
        if time_used_pct >= 0.75:
            return "tighten", f"Thesis {strength:.2f} — late in trade ({time_used_pct*100:.0f}% of time used), tightening"
        return "monitor", f"Thesis {strength:.2f} — monitoring"

    return "hold", f"Thesis {strength:.2f} — intact"


def _save_snapshot(thesis: ThesisState) -> None:
    try:
        from database import get_session, ThesisSnapshot

        thesis.snapshots.append({
            "ts":       time.time(),
            "move_pct": thesis.move_pct,
            "strength": thesis.thesis_strength,
            "action":   thesis.action,
        })

        if len(thesis.snapshots) > 100:
            thesis.snapshots = thesis.snapshots[-100:]

        pillars = thesis.pillars

        with get_session() as db:
            snap = ThesisSnapshot(
                trade_id              = thesis.trade_id,
                coin                  = thesis.coin,
                direction             = thesis.direction,
                grade                 = thesis.grade,
                sweep_valid           = pillars["sweep"].valid,
                sweep_score           = pillars["sweep"].score,
                zone_valid            = pillars["zone"].valid,
                zone_score            = pillars["zone"].score,
                structure_valid       = pillars["structure"].valid,
                structure_score       = pillars["structure"].score,
                btc_alignment_valid   = pillars["btc_alignment"].valid,
                btc_alignment_score   = pillars["btc_alignment"].score,
                regime_valid          = pillars["regime"].valid,
                regime_score          = pillars["regime"].score,
                thesis_strength       = thesis.thesis_strength,
                thesis_action         = thesis.action,
                live_price            = thesis.live_price,
                hours_open            = thesis.hours_open,
                move_pct              = thesis.move_pct,
                captured_move_pct     = thesis.captured_move_pct,
                velocity              = thesis.velocity,
                current_regime        = pillars["regime"].reason,
                entry_regime          = thesis.entry_regime,
                entry_thesis_strength = thesis.entry_thesis_strength,
                expected_move_pct     = thesis.expected_move_pct,
            )
            db.add(snap)

    except Exception as e:
        log.debug("_save_snapshot trade_id=%s: %s", thesis.trade_id, e)


def update_snapshot_outcome(trade_id: int, outcome: str, final_pnl: float) -> None:
    try:
        from database import SessionLocal, ThesisSnapshot
        with SessionLocal() as db:
            snapshots = db.query(ThesisSnapshot).filter(
                ThesisSnapshot.trade_id == trade_id,
                ThesisSnapshot.outcome.is_(None),
            ).all()
            for snap in snapshots:
                snap.outcome   = outcome
                snap.final_pnl = final_pnl
        log.debug(
            "Updated %s thesis snapshots with outcome for trade_id=%s",
            len(snapshots) if snapshots else 0, trade_id
        )
    except Exception as e:
        log.error("update_snapshot_outcome trade_id=%s: %s", trade_id, e)


def get_thesis_summary(trade_id: int) -> dict:
    thesis = _active_theses.get(trade_id)
    if not thesis:
        return {}

    pillars_summary = {}
    for name, pillar in thesis.pillars.items():
        pillars_summary[name] = {
            "valid":  pillar.valid,
            "score":  round(pillar.score, 3),
            "weight": pillar.weight,
            "reason": pillar.reason,
        }

    return {
        "trade_id":          thesis.trade_id,
        "coin":              thesis.coin,
        "direction":         thesis.direction,
        "grade":             thesis.grade,
        "thesis_strength":   thesis.thesis_strength,
        "action":            thesis.action,
        "action_reason":     thesis.action_reason,
        "hours_open":        thesis.hours_open,
        "move_pct":          thesis.move_pct,
        "captured_move_pct": thesis.captured_move_pct,
        "expected_move_pct": thesis.expected_move_pct,
        "velocity":          thesis.velocity,
        "velocity_stalled":  thesis.velocity_stalled,
        "stall_hours":       thesis.stall_hours,
        "pillars":           pillars_summary,
        "entry_regime":      thesis.entry_regime,
        "last_evaluated":    thesis.last_evaluated,
    }


def get_pillar_states_json(trade_id: int) -> str:
    thesis = _active_theses.get(trade_id)
    if not thesis:
        return "{}"
    pillars = {}
    for name, pillar in thesis.pillars.items():
        pillars[name] = {
            "valid":  pillar.valid,
            "score":  round(pillar.score, 3),
            "reason": pillar.reason,
        }
    return json.dumps(pillars)