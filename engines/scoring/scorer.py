import logging
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
    hour = datetime.now(timezone.utc).hour
    if 8  <= hour < 13: return "London"
    if 13 <= hour < 17: return "London/NY Overlap"
    if 17 <= hour < 21: return "New York"
    if 0  <= hour < 8:  return "Asia"
    return "Off Hours"