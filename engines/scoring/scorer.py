import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from config import cfg, HYBRID_SCORE_WEIGHTS, SCORE_THRESHOLDS

log = logging.getLogger(__name__)

HE = cfg.HYBRID_ENGINE


@dataclass
class ScoreComponent:
    name:      str
    score:     float
    max_score: float
    passed:    bool
    reason:    str = ""

    @property
    def pct(self) -> float:
        return round(self.score / self.max_score * 100, 1) if self.max_score > 0 else 0.0


@dataclass
class HybridScore:
    components:   list = field(default_factory=list)
    total:        float = 0.0
    max_possible: float = 0.0
    coin:         str   = ""
    direction:    str   = ""

    def add(
        self,
        name:      str,
        score:     float,
        max_score: float,
        passed:    bool,
        reason:    str = "",
    ) -> None:
        self.components.append(ScoreComponent(name, score, max_score, passed, reason))
        self.total        = round(self.total + score, 3)
        self.max_possible = round(self.max_possible + max_score, 3)

    def pct(self) -> float:
        if self.max_possible == 0:
            return 0.0
        return round(self.total / self.max_possible * 100, 1)

    def to_dict(self) -> dict:
        return {
            "coin":         self.coin,
            "direction":    self.direction,
            "total":        self.total,
            "max_possible": self.max_possible,
            "pct":          self.pct(),
            "components": [
                {
                    "name":      c.name,
                    "score":     c.score,
                    "max_score": c.max_score,
                    "pct":       c.pct,
                    "passed":    c.passed,
                    "reason":    c.reason,
                }
                for c in self.components
            ],
        }


def build_score(
    coin:          str,
    direction:     str,
    regime_result: object,
    trend_result:  object,
    reversion:     object,
    ict_result:    object,
    session:       str,
) -> HybridScore:
    hs           = HybridScore(coin=coin, direction=direction)
    weights      = HYBRID_SCORE_WEIGHTS
    total_weight = sum(weights.values())

    regime_score = _score_regime(regime_result)
    hs.add(
        "regime",
        regime_score * weights["regime"] / total_weight * 100,
        weights["regime"] / total_weight * 100,
        True,
        f"regime:{regime_result.label} adx:{regime_result.adx:.1f}",
    )

    trend_score = _score_trend(trend_result)
    hs.add(
        "trend",
        trend_score * weights["trend"] / total_weight * 100,
        weights["trend"] / total_weight * 100,
        True,
        f"direction:{trend_result.direction} strength:{trend_result.strength:.1f}",
    )

    rev_score = float(reversion.score) if reversion else 0.0
    hs.add(
        "reversion",
        rev_score * weights["reversion"] / total_weight * 100,
        weights["reversion"] / total_weight * 100,
        reversion.window_open if reversion else False,
        reversion.reason if reversion else "no_reversion",
    )

    ict_score = float(ict_result.score) if ict_result.confirmed else 0.0
    hs.add(
        "ict",
        ict_score * weights["ict"] / total_weight * 100,
        weights["ict"] / total_weight * 100,
        ict_result.confirmed,
        ict_result.desc,
    )

    btc_score = float(trend_result.btc_score) if trend_result else 0.0
    btc_max   = 10.0
    btc_norm  = max(0.0, min(btc_score / btc_max, 1.0))
    hs.add(
        "btc",
        btc_norm * weights["btc"] / total_weight * 100,
        weights["btc"] / total_weight * 100,
        True,
        trend_result.trace.get("btc", "") if trend_result else "",
    )

    session_score, session_reason = _score_session(session)
    hs.add(
        "session",
        session_score * weights["session"] / total_weight * 100,
        weights["session"] / total_weight * 100,
        True,
        session_reason,
    )

    return hs


def assign_grade(pct: float, regime_label: str) -> str:
    thresholds = _get_thresholds(regime_label)
    if pct >= thresholds["aplus"]:
        return "A+"
    if pct >= thresholds["a"]:
        return "A"
    if pct >= thresholds["b"]:
        return "B"
    return "F"


def score_ml(ml_probability: Optional[float], total_trades: int) -> tuple[float, str]:
    if ml_probability is None or total_trades < cfg.ML_MIN_TRADES:
        return 0.5, "ml_not_active"
    if ml_probability >= 0.75:
        return 1.0, f"ml_strong:{ml_probability:.2f}"
    if ml_probability >= 0.65:
        return 0.75, f"ml_positive:{ml_probability:.2f}"
    if ml_probability >= 0.55:
        return 0.50, f"ml_weak:{ml_probability:.2f}"
    return 0.20, f"ml_negative:{ml_probability:.2f}"


def get_session() -> str:
    hour = datetime.now(timezone.utc).hour
    if 8  <= hour < 13: return "London"
    if 13 <= hour < 17: return "London/NY Overlap"
    if 17 <= hour < 21: return "New York"
    if 0  <= hour < 8:  return "Asia"
    return "Off Hours"


def _score_regime(regime_result: object) -> float:
    if regime_result.is_trending:
        return 1.0
    if regime_result.is_ranging:
        return 0.65
    if regime_result.is_choppy:
        return 0.30
    if regime_result.is_volatile:
        return 0.15
    return 0.50


def _score_trend(trend_result: object) -> float:
    if not trend_result or not trend_result.passed:
        return 0.0
    adx = float(trend_result.adx)
    if adx >= 40:
        base = 1.0
    elif adx >= 30:
        base = 0.85
    elif adx >= 25:
        base = 0.70
    else:
        base = 0.55

    alignment = trend_result.alignment
    if alignment == "strong":
        base = min(1.0, base * 1.15)
    elif alignment == "opposing":
        base = base * 0.60
    elif alignment == "weak":
        base = base * 0.80

    return round(base, 3)


def _score_session(session: str) -> tuple[float, str]:
    s = (session or "").lower()
    if "london/ny" in s or "overlap" in s:
        return 1.0, "London/NY overlap — peak session"
    if "london" in s:
        return 0.75, "London session"
    if "new york" in s or "ny" in s:
        return 0.75, "New York session"
    if "asia" in s:
        return 0.20, "Asia session — low quality"
    return 0.35, "Off hours"


def _get_thresholds(regime_label: str) -> dict:
    mapping = {
        "trending": SCORE_THRESHOLDS["trending"],
        "ranging":  SCORE_THRESHOLDS["ranging"],
        "choppy":   SCORE_THRESHOLDS["choppy"],
        "volatile": SCORE_THRESHOLDS["volatile"],
    }
    return mapping.get(regime_label, SCORE_THRESHOLDS["default"])