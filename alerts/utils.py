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
        log.error(f"Grade accuracy error: {e}")
        return ""


def categorize_results(results: list) -> dict:
    return {
        "tradeable": [
            r for r in results
            if r.get("grade") in ["A+", "A"] and
            r.get("direction") in ["LONG", "SHORT"]
        ],
        "watching": [
            r for r in results
            if r.get("grade") == "B" and
            r.get("direction") in ["LONG", "SHORT"]
        ],
        "skipped": [
            r for r in results
            if r.get("grade") == "B"
        ],
        "building": [
            r for r in results
            if r.get("grade") == "C"
        ]
    }