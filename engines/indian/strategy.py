from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import logging

log = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))

MIN_ORB_SIZE     = 200
MAX_ORB_SIZE     = 350
ENTRY_BUFFER     = 10
SL_MULT          = 0.3
TP_MULT          = 1.0
TP2_MULT         = 1.5
ENTRY_START_H    = 11
ENTRY_END_H      = 12
SKIP_WEEKS       = [3]
MIN_PRE_RANGE    = 300
MIN_PREV_RANGE   = 600
TIME_EXIT_HOUR   = 14
TIME_EXIT_MINUTE = 30
MIN_DAY_RANGE    = 500


@dataclass
class ORBSignal:
    signal:      bool
    instrument:  str
    direction:   str
    entry:       float
    sl:          float
    tp1:         float
    tp2:         float
    orb_high:    float
    orb_low:     float
    orb_size:    float
    sl_pts:      float
    tp_pts:      float
    rr1:         float
    rr2:         float
    pre_range:   float
    prev_range:  float
    week:        int
    reason:      str


def get_week_of_month(d) -> int:
    return (d.day - 1) // 7 + 1


def analyze(
    instrument:    str,
    orb_high:      float,
    orb_low:       float,
    current_price: float,
    current_hour:  int,
    current_minute:int,
    pre_range:     float = 0.0,
    prev_range:    float = 0.0,
    current_volume:float = 0,
    avg_volume:    float = 0,
) -> ORBSignal:
    try:
        now      = datetime.now(IST)
        week     = get_week_of_month(now.date())
        orb_size = round(orb_high - orb_low, 2)

        if week in SKIP_WEEKS:
            return _no(instrument, f'skip_week_{week}', orb_high, orb_low, orb_size, pre_range, prev_range, week)

        if orb_size < MIN_ORB_SIZE:
            return _no(instrument, f'orb_too_tight:{orb_size:.0f}', orb_high, orb_low, orb_size, pre_range, prev_range, week)

        if orb_size > MAX_ORB_SIZE:
            return _no(instrument, f'orb_too_wide:{orb_size:.0f}', orb_high, orb_low, orb_size, pre_range, prev_range, week)

        if current_hour < ENTRY_START_H:
            return _no(instrument, 'before_entry_window', orb_high, orb_low, orb_size, pre_range, prev_range, week)

        if current_hour > ENTRY_END_H or (current_hour == ENTRY_END_H and current_minute > 0):
            return _no(instrument, 'after_entry_window', orb_high, orb_low, orb_size, pre_range, prev_range, week)

        if pre_range < MIN_PRE_RANGE and prev_range < MIN_PREV_RANGE:
            return _no(
                instrument,
                f'low_volatility:pre={pre_range:.0f}<{MIN_PRE_RANGE}_prev={prev_range:.0f}<{MIN_PREV_RANGE}',
                orb_high, orb_low, orb_size, pre_range, prev_range, week
            )

        short_entry = orb_low - ENTRY_BUFFER

        if current_price > short_entry:
            return _no(instrument, 'no_breakdown', orb_high, orb_low, orb_size, pre_range, prev_range, week)

        sl_pts  = round(orb_size * SL_MULT)
        tp_pts  = round(orb_size * TP_MULT)
        tp2_pts = round(orb_size * TP2_MULT)

        entry   = current_price
        sl      = round(entry + sl_pts,  2)
        tp1     = round(entry - tp_pts,  2)
        tp2     = round(entry - tp2_pts, 2)

        sl_dist = abs(entry - sl)
        rr1     = round(abs(tp1 - entry) / sl_dist, 2) if sl_dist > 0 else 0
        rr2     = round(abs(tp2 - entry) / sl_dist, 2) if sl_dist > 0 else 0

        return ORBSignal(
            signal     = True,
            instrument = instrument,
            direction  = 'SHORT',
            entry      = entry,
            sl         = sl,
            tp1        = tp1,
            tp2        = tp2,
            orb_high   = orb_high,
            orb_low    = orb_low,
            orb_size   = orb_size,
            sl_pts     = sl_pts,
            tp_pts     = tp_pts,
            rr1        = rr1,
            rr2        = rr2,
            pre_range  = pre_range,
            prev_range = prev_range,
            week       = week,
            reason     = '',
        )

    except Exception as e:
        log.error('strategy.analyze %s: %s', instrument, e)
        return _no(instrument, str(e), 0, 0, 0, 0, 0, 0)


def _no(
    instrument: str,
    reason:     str,
    orb_high:   float,
    orb_low:    float,
    orb_size:   float,
    pre_range:  float,
    prev_range: float,
    week:       int,
) -> ORBSignal:
    return ORBSignal(
        signal     = False,
        instrument = instrument,
        direction  = 'NEUTRAL',
        entry      = 0.0,
        sl         = 0.0,
        tp1        = 0.0,
        tp2        = 0.0,
        orb_high   = orb_high,
        orb_low    = orb_low,
        orb_size   = orb_size,
        sl_pts     = 0.0,
        tp_pts     = 0.0,
        rr1        = 0.0,
        rr2        = 0.0,
        pre_range  = pre_range,
        prev_range = prev_range,
        week       = week,
        reason     = reason,
    )