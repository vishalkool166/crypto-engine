from dataclasses import dataclass
import logging

log = logging.getLogger(__name__)

MIN_ORB_SIZE   = 150
MAX_ORB_SIZE   = 500
MIN_DAY_RANGE  = 500
ENTRY_BUFFER   = 10
SL_POINTS      = 150
TP_POINTS      = 300
ENTRY_START_H  = 10
ENTRY_END_H    = 12
NO_SHORT_UNTIL = 11


@dataclass
class ORBSignal:
    signal:     bool
    instrument: str
    direction:  str
    entry:      float
    sl:         float
    tp1:        float
    tp2:        float
    orb_high:   float
    orb_low:    float
    orb_size:   float
    rr1:        float
    rr2:        float
    volume_ok:  bool
    reason:     str


def analyze(
    instrument:     str,
    orb_high:       float,
    orb_low:        float,
    current_price:  float,
    current_hour:   int,
    current_minute: int,
    day_range:      float,
    current_volume: float = 0,
    avg_volume:     float = 0,
) -> ORBSignal:
    try:
        orb_size = round(orb_high - orb_low, 2)

        if current_hour < ENTRY_START_H:
            return _no_signal(instrument, 'before_entry_window')

        if current_hour > ENTRY_END_H:
            return _no_signal(instrument, 'after_entry_window')

        if day_range < MIN_DAY_RANGE:
            return _no_signal(instrument, f'day_range_too_small:{day_range:.0f}')

        if orb_size < MIN_ORB_SIZE:
            return _no_signal(instrument, f'orb_too_tight:{orb_size:.0f}')

        if orb_size > MAX_ORB_SIZE:
            return _no_signal(instrument, f'orb_too_wide:{orb_size:.0f}')

        long_entry  = orb_high + ENTRY_BUFFER
        short_entry = orb_low  - ENTRY_BUFFER

        if current_price >= long_entry:
            direction = 'LONG'
        elif current_price <= short_entry:
            direction = 'SHORT'
        else:
            return _no_signal(instrument, 'no_breakout')

        if direction == 'SHORT' and current_hour < NO_SHORT_UNTIL:
            return _no_signal(instrument, 'no_short_before_11am')

        entry   = current_price
        sl      = round(entry - SL_POINTS, 2) if direction == 'LONG' else round(entry + SL_POINTS, 2)
        tp1     = round(entry + TP_POINTS, 2) if direction == 'LONG' else round(entry - TP_POINTS, 2)
        tp2     = round(entry + TP_POINTS * 2, 2) if direction == 'LONG' else round(entry - TP_POINTS * 2, 2)
        sl_dist = abs(entry - sl)
        rr1     = round(abs(tp1 - entry) / sl_dist, 2) if sl_dist > 0 else 0
        rr2     = round(abs(tp2 - entry) / sl_dist, 2) if sl_dist > 0 else 0

        volume_ok = True
        if avg_volume > 0 and current_volume > 0:
            volume_ok = current_volume >= avg_volume * 0.8

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
            rr1        = rr1,
            rr2        = rr2,
            volume_ok  = volume_ok,
            reason     = '',
        )

    except Exception as e:
        log.error('strategy.analyze %s: %s', instrument, e)
        return _no_signal(instrument, str(e))


def _no_signal(instrument: str, reason: str) -> ORBSignal:
    return ORBSignal(
        signal     = False,
        instrument = instrument,
        direction  = 'NEUTRAL',
        entry      = 0.0,
        sl         = 0.0,
        tp1        = 0.0,
        tp2        = 0.0,
        orb_high   = 0.0,
        orb_low    = 0.0,
        orb_size   = 0.0,
        rr1        = 0.0,
        rr2        = 0.0,
        volume_ok  = False,
        reason     = reason,
    )