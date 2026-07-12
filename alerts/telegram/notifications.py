import logging
from collections import deque
from datetime import datetime, timezone, timedelta
from alerts.telegram.client     import send
from alerts.telegram.formatters import now_ist, get_stats, get_in_trade_count
from config import cfg

log = logging.getLogger(__name__)

IST             = timezone(timedelta(hours=5, minutes=30))
_sent_signals:  deque = deque(maxlen=100)
_skip_reasons:  dict  = {}
_SKIP_TTL               = 3600


def _is_skipped(coin: str) -> bool:
    ts = _skip_reasons.get(coin)
    if ts is None:
        return False
    import time
    if time.time() - ts > _SKIP_TTL:
        del _skip_reasons[coin]
        return False
    return True


async def send_signal(signal: dict, coin: str, regime: str, session: str) -> None:
    if signal.get("grade") not in cfg.MIN_GRADE_TO_TRADE:
        return
    if signal.get("direction") not in ("LONG", "SHORT"):
        return
    if not signal.get("entry") or _is_skipped(coin):
        return

    sig_key = (
        f"{coin}_{signal.get('direction')}_"
        f"{signal.get('grade')}_"
        f"{round(signal.get('entry', 0), 0)}"
    )
    if sig_key in _sent_signals:
        return
    _sent_signals.append(sig_key)

    grade     = signal.get("grade",     "?")
    direction = signal.get("direction", "?")
    score     = signal.get("score",     0)
    entry     = signal.get("entry",     0)
    sl        = signal.get("sl",        0)
    tp1       = signal.get("tp1",       0)
    tp2       = signal.get("tp2")
    sl_pct    = signal.get("sl_pct",    0)
    risk_amt  = signal.get("risk_amt",  0)
    pos_size  = signal.get("pos_size",  0)
    rr1       = signal.get("rr1",       0)
    narrative = signal.get("narrative", "")

    emoji      = "🏆" if grade == "A+" else "✅" if grade == "A" else "👀"
    dir_emoji  = "📈" if direction == "LONG" else "📉"
    grade_note = "_Grade B — paper mode only_\n\n" if grade == "B" else ""

    msg = (
        f"{emoji} *Grade {grade} — {direction}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"*{coin}USDT — {dir_emoji} {direction}*\n"
        f"Score:   `{score:.2f}`\n"
        f"Version: `{cfg.SYSTEM_VERSION}`\n"
        f"Time:    `{now_ist()}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Entry:   `{entry:.4f}`\n"
        f"SL:      `{sl:.4f}` ({sl_pct:.2f}%)\n"
        f"TP1:     `{tp1:.4f}` ({rr1:.1f}R)\n"
    )

    if tp2:
        rr2  = signal.get("rr2", 0)
        msg += f"TP2:     `{tp2:.4f}` ({rr2:.1f}R)\n"

    msg += (
        f"\n━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Risk:    `${risk_amt:.2f}`\n"
        f"Size:    `${pos_size:.2f}`\n\n"
        f"{grade_note}"
        f"{narrative}\n\n"
        f"_Signal forwarded to execution engine._"
    )

    await send(msg)


async def send_scan_summary(results: list) -> None:
    from scheduler import get_next_scan_time
    from engines.state import get as get_coin_state

    next_scan      = get_next_scan_time()
    total          = len(results)
    watching       = [r for r in results if r.get("state") == "watching"]
    idle           = [r for r in results if r.get("state") == "idle"]
    tradeable      = [
        r for r in results
        if r.get("grade") in ("A+", "A")
        and r.get("direction") in ("LONG", "SHORT")
    ]
    in_trade_count = get_in_trade_count()

    if tradeable:
        lines = [
            f"🎯 *Signal Fired — {now_ist()}*\n"
            f"{len(tradeable)} signal(s) confirmed\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
        ]
        for r in tradeable[:3]:
            direction = r.get("direction", "--")
            dir_emoji = "📈" if direction == "LONG" else "📉"
            lines.append(
                f"{dir_emoji} *{r['coin']}* — `{direction}` "
                f"Grade `{r.get('grade', '--')}` "
                f"Score `{r.get('score', 0):.2f}`\n"
            )
        lines.append(f"\nNext scan: `{next_scan}`")
        await send("\n".join(lines))
        return

    lines = [
        f"🔍 *Scan Complete — {now_ist()}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Total coins:  `{total}`\n"
        f"Watching:     `{len(watching)}`\n"
        f"In trade:     `{in_trade_count}`\n"
        f"Idle:         `{len(idle)}`\n"
    ]

    if watching:
        lines.append("\n*⚡ Watching Zones:*")
        for r in watching[:3]:
            s         = get_coin_state(r["coin"])
            setup     = s.get("setup") or {}
            direction = setup.get("direction", "--")
            zone      = setup.get("zone", {}) or {}
            dist      = zone.get("distance_pct", 0)
            dir_emoji = "📈" if direction == "LONG" else "📉"
            lines.append(
                f"{dir_emoji} `{r['coin']}` — `{direction}` · `{dist:.2f}%` from zone"
            )

    lines.append(f"\nNext scan: `{next_scan}`")
    await send("\n".join(lines))