from datetime import datetime, timezone, timedelta
from database import get_session, Signal
import logging

log = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))


def now_ist() -> str:
    return datetime.now(IST).strftime("%I:%M %p IST")


def now_ist_str() -> str:
    return datetime.now(IST).strftime("%d %b · %I:%M %p IST")


def grade_accuracy_str(grade: str) -> str:
    try:
        with get_session() as db:
            signals = db.query(Signal).filter(
                Signal.grade     == grade,
                Signal.outcome.in_(["win", "loss"])
            ).all()
            if not signals:
                return f"Grade {grade} accuracy: no data yet"
            wins  = sum(1 for s in signals if s.outcome == "win")
            total = len(signals)
            wr    = round(wins / total * 100, 1)
            return f"Grade {grade} accuracy: `{wins}W {total - wins}L` — `{wr}% win rate`"
    except Exception as e:
        log.error("Grade accuracy error: %s", e)
        return ""


def categorize_results(results: list) -> dict:
    tradeable = []
    watching  = []
    building  = []
    skipped   = []

    for r in results:
        state     = r.get("state", "")
        direction = r.get("direction", "")
        grade     = r.get("grade", "")

        if state in ("signal_ready", "zone_active") and direction in ("LONG", "SHORT"):
            if grade in ("A+", "A"):
                tradeable.append(r)
            elif grade == "B":
                watching.append(r)
            else:
                building.append(r)

        elif state == "bias_defined":
            building.append(r)

        elif state in ("no_bias", "cooldown"):
            skipped.append(r)

    return {
        "tradeable": tradeable,
        "watching":  watching,
        "building":  building,
        "skipped":   skipped,
    }