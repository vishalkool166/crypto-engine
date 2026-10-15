import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone

log = logging.getLogger(__name__)


@dataclass
class ScoreResult:
    total:     float
    grade:     str
    adx_pts:   float
    rsi_pts:   float
    vol_pts:   float
    direction: str
    regime:    str


def score(
    adx:       float,
    rsi:       float,
    vol_ratio: float,
    direction: str,
    regime:    str,
) -> ScoreResult:
    if direction not in ("LONG", "SHORT") or not all(
        isinstance(v, (int, float)) and math.isfinite(v) for v in (adx, rsi, vol_ratio)
    ) or adx < 0 or not 0 <= rsi <= 100 or vol_ratio < 0:
        return ScoreResult(total=0.0, grade="F", adx_pts=0.0,
                           rsi_pts=0.0, vol_pts=0.0,
                           direction=direction, regime=regime)
    adx_pts = _adx_score(adx)
    rsi_pts = _rsi_score(rsi, direction)
    vol_pts = _vol_score(vol_ratio)

    total = adx_pts + rsi_pts + vol_pts
    grade = _grade(total)

    return ScoreResult(
        total     = round(total, 1),
        grade     = grade,
        adx_pts   = adx_pts,
        rsi_pts   = rsi_pts,
        vol_pts   = vol_pts,
        direction = direction,
        regime    = regime,
    )


def _adx_score(adx: float) -> float:
    if adx >= 30:
        return 40.0
    if adx >= 25:
        return 30.0
    if adx >= 20:
        return 20.0
    return 0.0


def _rsi_score(rsi: float, direction: str) -> float:
    if direction == "LONG":
        if 40 <= rsi <= 45:
            return 30.0
        if 45 <= rsi <= 50:
            return 20.0
        if 50 <= rsi <= 65:
            return 10.0
        return 0.0
    else:
        if 55 <= rsi <= 60:
            return 30.0
        if 50 <= rsi <= 55:
            return 20.0
        if 35 <= rsi <= 50:
            return 10.0
        return 0.0


def _vol_score(vol_ratio: float) -> float:
    if vol_ratio >= 2.0:
        return 30.0
    if vol_ratio >= 1.5:
        return 20.0
    if vol_ratio >= 1.0:
        return 10.0
    return 0.0


def _grade(total: float) -> str:
    if total >= 80:
        return "A+"
    if total >= 65:
        return "A"
    if total >= 50:
        return "B"
    return "F"


def get_session() -> str:
    """Compatibility wrapper around the shared UTC session policy."""
    from engines.core.sessions import session_at
    return session_at(datetime.now(timezone.utc))
