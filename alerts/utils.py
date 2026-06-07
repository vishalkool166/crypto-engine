from datetime import datetime, timezone, timedelta
from database import get_session, Trade
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
            trades = db.query(Trade).filter(
                Trade.grade     == grade,
                Trade.is_active == False,
                Trade.outcome.in_(["win", "loss"])
            ).all()
            if not trades:
                return f"Grade {grade} accuracy: no data yet"
            wins  = sum(1 for t in trades if t.outcome == "win")
            total = len(trades)
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
        "building": [
            r for r in results
            if r.get("grade") == "C"
        ]
    }