import logging
from collections import deque
from datetime import datetime, timezone, timedelta
from alerts.telegram.client import send
from config import cfg

log = logging.getLogger(__name__)

IST            = timezone(timedelta(hours=5, minutes=30))
_sent_signals: deque = deque(maxlen=100)
_SKIP_TTL              = 3600


def _now_ist() -> str:
    return datetime.now(IST).strftime("%I:%M %p IST")


def _grade_emoji(grade: str) -> str:
    return {"A+": "🏆", "A": "⭐", "B": "👀"}.get(grade, "📊")


def _dir_emoji(direction: str) -> str:
    return "📈" if direction == "LONG" else "📉"


async def send_signal(signal: dict, coin: str, regime: str, session: str) -> None:
    if signal.get("grade") not in cfg.MIN_GRADE_TO_TRADE:
        return
    if signal.get("direction") not in ("LONG", "SHORT"):
        return
    if not signal.get("entry"):
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
    rr2       = signal.get("rr2",       0)

    g_emoji   = _grade_emoji(grade)
    d_emoji   = _dir_emoji(direction)
    mode      = "🔴 LIVE" if not cfg.PAPER_TRADING else "🔵 PAPER"

    msg = (
        f"{g_emoji} *Grade {grade} Signal — {coin}USDT*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{d_emoji} *{direction}*  ·  Score `{score:.1f}`  ·  {mode}\n"
        f"🕐 `{_now_ist()}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 Entry:    `{entry:.4f}`\n"
        f"🛑 SL:       `{sl:.4f}` ({sl_pct:.2f}%)\n"
        f"✅ TP1:      `{tp1:.4f}` ({rr1:.1f}R)\n"
    )

    if tp2:
        msg += f"🚀 TP2:      `{tp2:.4f}` ({rr2:.1f}R)\n"

    msg += (
        f"\n━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Risk:     `${risk_amt:.2f}`\n"
        f"📦 Size:     `${pos_size:.2f}`\n"
        f"📍 Regime:   `{regime or '--'}`\n"
        f"⏰ Session:  `{session or '--'}`\n\n"
        f"_Forwarded to execution engine_"
    )

    await send(msg)


async def send_scan_summary(results: list) -> None:
    from scheduler import get_next_scan_time
    from engines.state import get as get_coin_state
    from database import SessionLocal
    from database import Trade as TradeModel

    next_scan = get_next_scan_time()
    mode      = "🔴 LIVE" if not cfg.PAPER_TRADING else "🔵 PAPER"

    try:
        with SessionLocal() as db:
            in_trade_count = db.query(TradeModel).filter(
                TradeModel.is_active == True
            ).count()
    except Exception:
        in_trade_count = 0

    live = [
        r for r in results
        if r.get("grade") in ("A+", "A", "B")
        and r.get("direction") in ("LONG", "SHORT")
        and r.get("score", 0) > 0
    ]

    watching = [r for r in results if r.get("state") == "watching"]

    if live:
        lines = [
            f"🎯 *Signal Fired — {_now_ist()}*\n"
            f"`{len(live)}` signal(s) confirmed\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
        ]
        for r in live[:3]:
            g_emoji = _grade_emoji(r.get("grade", "--"))
            d_emoji = _dir_emoji(r.get("direction", "--"))
            lines.append(
                f"{g_emoji} *{r['coin']}*  {d_emoji} `{r.get('direction', '--')}`  "
                f"Score `{r.get('score', 0):.1f}`"
            )
        lines.append(f"\n🕐 Next scan: `{next_scan}`")
        await send("\n".join(lines))
        return

    watching_count = len(watching)
    idle_count     = len(results) - watching_count - in_trade_count

    lines = [
        f"🔍 *Scan Complete — {_now_ist()}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 Coins scanned:  `{len(results)}`\n"
        f"⚡ Watching:       `{watching_count}`\n"
        f"🔥 In trade:       `{in_trade_count}`\n"
        f"😴 Idle:           `{idle_count}`\n"
    ]

    if watching:
        lines.append(f"\n*⚡ Active Watches:*")
        for r in watching[:3]:
            d_emoji = _dir_emoji(r.get("direction", "--"))
            lines.append(
                f"  {d_emoji} `{r['coin']}` — Score `{r.get('score', 0):.1f}`"
            )

    lines.append(f"\n{mode}  ·  🕐 Next: `{next_scan}`")
    await send("\n".join(lines))