import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)


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
    instrument:  str,
    orb_high:    float,
    orb_low:     float,
    current_price: float,
    current_volume: float,
    avg_volume:  float,
    buffer_pct:  float = 0.05,
    vol_mult:    float = 1.2,
    rr_min:      float = 1.5,
) -> ORBSignal:
    try:
        orb_size = round(orb_high - orb_low, 2)

        if orb_size <= 0:
            return _no_signal(instrument, "orb_size_zero")

        if orb_size > orb_high * 0.03:
            return _no_signal(instrument, f"orb_too_wide:{orb_size:.0f}")

        buffer     = orb_high * buffer_pct / 100
        long_entry = orb_high + buffer
        short_entry= orb_low  - buffer

        volume_ok  = current_volume >= avg_volume * vol_mult if avg_volume > 0 else True

        if current_price > long_entry:
            direction = "LONG"
            entry     = round(current_price, 2)
            sl        = round(orb_low - buffer, 2)
            sl_dist   = abs(entry - sl)

            if sl_dist <= 0:
                return _no_signal(instrument, "sl_dist_zero")

            tp1 = round(entry + sl_dist * rr_min, 2)
            tp2 = round(entry + sl_dist * 2.5,    2)
            rr1 = round(abs(tp1 - entry) / sl_dist, 2)
            rr2 = round(abs(tp2 - entry) / sl_dist, 2)

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
                reason     = "",
            )

        elif current_price < short_entry:
            direction = "SHORT"
            entry     = round(current_price, 2)
            sl        = round(orb_high + buffer, 2)
            sl_dist   = abs(entry - sl)

            if sl_dist <= 0:
                return _no_signal(instrument, "sl_dist_zero")

            tp1 = round(entry - sl_dist * rr_min, 2)
            tp2 = round(entry - sl_dist * 2.5,    2)
            rr1 = round(abs(tp1 - entry) / sl_dist, 2)
            rr2 = round(abs(tp2 - entry) / sl_dist, 2)

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
                reason     = "",
            )

        else:
            return _no_signal(instrument, "no_breakout")

    except Exception as e:
        log.error("strategy.analyze %s: %s", instrument, e)
        return _no_signal(instrument, str(e))


def _no_signal(instrument: str, reason: str) -> ORBSignal:
    return ORBSignal(
        signal     = False,
        instrument = instrument,
        direction  = "NEUTRAL",
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