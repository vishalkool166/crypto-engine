from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import logging
from config import get_indian_instrument_config

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
        inst_cfg = get_indian_instrument_config(instrument)

        direction       = inst_cfg.get("direction",      "SHORT")
        min_orb         = inst_cfg.get("min_orb",        MIN_ORB_SIZE)
        max_orb         = inst_cfg.get("max_orb",        MAX_ORB_SIZE)
        sl_mult         = inst_cfg.get("sl_mult",        SL_MULT)
        tp_mult         = inst_cfg.get("tp_mult",        TP_MULT)
        tp2_mult        = inst_cfg.get("tp2_mult",       TP2_MULT)
        entry_buffer    = inst_cfg.get("entry_buffer",   ENTRY_BUFFER)
        min_pre         = inst_cfg.get("min_pre_range",  MIN_PRE_RANGE)
        min_prev        = inst_cfg.get("min_prev_range", MIN_PREV_RANGE)
        skip_weeks      = inst_cfg.get("skip_weeks",     SKIP_WEEKS)
        entry_start_h   = inst_cfg.get("entry_start_h",  ENTRY_START_H)
        entry_end_h     = inst_cfg.get("entry_end_h",    ENTRY_END_H)

        now      = datetime.now(IST)
        week     = get_week_of_month(now.date())
        orb_size = round(orb_high - orb_low, 2)

        if week in skip_weeks:
            return _no(instrument, f'skip_week_{week}', orb_high, orb_low, orb_size, pre_range, prev_range, week)

        if orb_size < min_orb:
            return _no(instrument, f'orb_too_tight:{orb_size:.0f}', orb_high, orb_low, orb_size, pre_range, prev_range, week)

        if orb_size > max_orb:
            return _no(instrument, f'orb_too_wide:{orb_size:.0f}', orb_high, orb_low, orb_size, pre_range, prev_range, week)

        if current_hour < entry_start_h:
            return _no(instrument, 'before_entry_window', orb_high, orb_low, orb_size, pre_range, prev_range, week)

        if current_hour > entry_end_h or (current_hour == entry_end_h and current_minute > 0):
            return _no(instrument, 'after_entry_window', orb_high, orb_low, orb_size, pre_range, prev_range, week)

        if pre_range < min_pre and prev_range < min_prev:
            return _no(
                instrument,
                f'low_volatility:pre={pre_range:.0f}<{min_pre}_prev={prev_range:.0f}<{min_prev}',
                orb_high, orb_low, orb_size, pre_range, prev_range, week
            )

        if direction == 'SHORT':
            entry_trigger = orb_low - entry_buffer
            if current_price > entry_trigger:
                return _no(instrument, 'no_breakdown', orb_high, orb_low, orb_size, pre_range, prev_range, week)
        else:
            entry_trigger = orb_high + entry_buffer
            if current_price < entry_trigger:
                return _no(instrument, 'no_breakout', orb_high, orb_low, orb_size, pre_range, prev_range, week)

        sl_pts  = round(orb_size * sl_mult)
        tp_pts  = round(orb_size * tp_mult)
        tp2_pts = round(orb_size * tp2_mult)

        entry = current_price

        if direction == 'SHORT':
            sl  = round(entry + sl_pts,  2)
            tp1 = round(entry - tp_pts,  2)
            tp2 = round(entry - tp2_pts, 2)
        else:
            sl  = round(entry - sl_pts,  2)
            tp1 = round(entry + tp_pts,  2)
            tp2 = round(entry + tp2_pts, 2)

        sl_dist = abs(entry - sl)
        rr1     = round(abs(tp1 - entry) / sl_dist, 2) if sl_dist > 0 else 0
        rr2     = round(abs(tp2 - entry) / sl_dist, 2) if sl_dist > 0 else 0

        return ORBSignal(
            signal     = True,
            instrument = instrument,
            direction  = direction,
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