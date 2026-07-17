from dataclasses import dataclass, field
from typing import Optional
from config import cfg


@dataclass
class ScoreComponent:
    name: str
    score: float
    max_score: float
    passed: bool
    reason: str = ""


@dataclass
class SignalScore:
    components: list = field(default_factory=list)
    total: float = 0.0
    max_possible: float = 0.0
    grade: str = "F"
    passed: bool = False
    stopped_at: Optional[str] = None
    direction: str = ""
    coin: str = ""

    def add(self, name: str, score: float, max_score: float, passed: bool, reason: str = ""):
        self.components.append(ScoreComponent(name, score, max_score, passed, reason))
        self.total = round(self.total + score, 3)
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
            "grade":        self.grade,
            "passed":       self.passed,
            "stopped_at":   self.stopped_at,
            "components":   [
                {
                    "name":      c.name,
                    "score":     c.score,
                    "max_score": c.max_score,
                    "passed":    c.passed,
                    "reason":    c.reason,
                }
                for c in self.components
            ],
        }


SCORE_WEIGHTS = {
    "ema_context":      {"max": 10, "required": True},
    "btc_context":      {"max": 10, "required": False},
    "htf_alignment":    {"max": 12, "required": False},
    "sweep":            {"max": 25, "required": True},
    "zone":             {"max": 22, "required": True},
    "trigger":          {"max": 18, "required": True},
    "session":          {"max": 6,  "required": False},
    "ml":               {"max": 8,  "required": False},
    "risk":             {"max": 0,  "required": True},
}

GRADE_THRESHOLDS = {
    "trending":  {"aplus": 85, "a": 68, "b": 52},
    "ranging":   {"aplus": 78, "a": 62, "b": 48},
    "choppy":    {"aplus": 88, "a": 72, "b": 56},
    "volatile":  {"aplus": 90, "a": 75, "b": 58},
    "default":   {"aplus": 85, "a": 68, "b": 52},
}


def get_thresholds(regime: str) -> dict:
    r = (regime or "").lower()
    if "trend" in r:
        return GRADE_THRESHOLDS["trending"]
    if "rang" in r:
        return GRADE_THRESHOLDS["ranging"]
    if "chop" in r:
        return GRADE_THRESHOLDS["choppy"]
    if "volat" in r or "panic" in r:
        return GRADE_THRESHOLDS["volatile"]
    return GRADE_THRESHOLDS["default"]


def assign_grade(pct: float, regime: str) -> str:
    t = get_thresholds(regime)
    if pct >= t["aplus"]:
        return "A+"
    if pct >= t["a"]:
        return "A"
    if pct >= t["b"]:
        return "B"
    return "F"


def score_btc_context(btc_cls: str, btc_adx: float, direction: str) -> tuple[float, str]:
    max_score = SCORE_WEIGHTS["btc_context"]["max"]
    is_long = direction == "LONG"

    if btc_cls == "neutral":
        return 5.0, "BTC neutral"

    if is_long:
        if btc_cls == "bull":
            if btc_adx >= 30:
                return max_score, f"BTC strongly bullish ADX:{btc_adx:.0f}"
            return 7.0, f"BTC bullish ADX:{btc_adx:.0f}"
        else:
            if btc_adx >= 35:
                return -8.0, f"BTC strongly bearish ADX:{btc_adx:.0f}"
            if btc_adx >= 25:
                return -4.0, f"BTC bearish ADX:{btc_adx:.0f}"
            return 0.0, f"BTC weakly bearish ADX:{btc_adx:.0f}"
    else:
        if btc_cls == "bear":
            if btc_adx >= 30:
                return max_score, f"BTC strongly bearish ADX:{btc_adx:.0f}"
            return 7.0, f"BTC bearish ADX:{btc_adx:.0f}"
        else:
            if btc_adx >= 35:
                return -8.0, f"BTC strongly bullish ADX:{btc_adx:.0f}"
            if btc_adx >= 25:
                return -4.0, f"BTC bullish ADX:{btc_adx:.0f}"
            return 0.0, f"BTC weakly bullish ADX:{btc_adx:.0f}"


def score_htf_alignment(daily_bias: str, weekly_bias: str, direction: str) -> tuple[float, str]:
    max_score = SCORE_WEIGHTS["htf_alignment"]["max"]
    opposite = "SHORT" if direction == "LONG" else "LONG"

    daily_match  = daily_bias  == direction
    weekly_match = weekly_bias == direction
    daily_opp    = daily_bias  == opposite
    weekly_opp   = weekly_bias == opposite

    if daily_opp and weekly_opp:
        return -10.0, "Daily and weekly both opposing"
    if daily_opp:
        return -5.0, f"Daily opposing direction"
    if weekly_opp:
        return -3.0, f"Weekly opposing direction"
    if daily_match and weekly_match:
        return max_score, "Daily and weekly both aligned"
    if daily_match or weekly_match:
        return 7.0, "One timeframe aligned"
    return 4.0, "Both timeframes neutral"


def score_session(session: str) -> tuple[float, str]:
    max_score = SCORE_WEIGHTS["session"]["max"]
    s = (session or "").lower()
    if "london/ny" in s or "overlap" in s:
        return max_score, "London/NY overlap — peak session"
    if "london" in s:
        return 4.0, "London session"
    if "new york" in s or "ny" in s:
        return 4.0, "New York session"
    if "asia" in s:
        return 1.0, "Asia session — low quality"
    return 2.0, "Off hours"


def score_ml(ml_probability: float | None, total_trades: int) -> tuple[float, str]:
    max_score = SCORE_WEIGHTS["ml"]["max"]
    if ml_probability is None or total_trades < cfg.ML_MIN_TRADES:
        return 4.0, "ML not active — neutral"
    if ml_probability >= 0.75:
        return max_score, f"ML strong {ml_probability:.2f}"
    if ml_probability >= 0.65:
        return 5.0, f"ML positive {ml_probability:.2f}"
    if ml_probability >= 0.55:
        return 2.0, f"ML weak {ml_probability:.2f}"
    return -2.0, f"ML negative {ml_probability:.2f}"