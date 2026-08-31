import json
import logging
import time
from datetime import datetime, timezone
from database import get_session, Signal as SignalModel
from config import cfg
from engines.crypto.strategy import SignalResult

log = logging.getLogger(__name__)


def save_signal(result: SignalResult) -> int | None:
    if not result.signal:
        return None
    if result.grade not in cfg.MIN_GRADE_TO_TRADE:
        return None
    if result.direction not in ("LONG", "SHORT"):
        return None
    if not result.entry:
        return None
    if result.rr1 < 2.0:
        return None

    try:
        with get_session() as db:
            existing = db.query(SignalModel).filter(
                SignalModel.coin      == result.coin,
                SignalModel.direction == result.direction,
                SignalModel.outcome   == "pending",
            ).first()

            if existing:
                from trade.executor import has_open_trade
                if has_open_trade(result.coin):
                    return None
                existing.outcome = "expired"

            now = datetime.now(timezone.utc)

            row = SignalModel(
                coin          = result.coin,
                direction     = result.direction,
                grade         = result.grade,
                score         = result.score,
                signal_type   = "MOMENTUM",
                entry         = result.entry,
                sl            = result.sl,
                tp1           = result.tp1,
                tp2           = result.tp2,
                sl_pct        = result.sl_pct,
                risk_amt      = result.risk_amt,
                risk_pct      = result.risk_pct,
                position      = result.pos_size,
                leverage      = str(result.leverage) + "x",
                sweep_score   = 0.0,
                retest_score  = 0.0,
                disp_score    = 0.0,
                funding       = 0.0,
                oi_signal     = "",
                outcome       = "pending",
                day_of_week   = now.weekday(),
                hour_of_day   = now.hour,
                system_version= cfg.SYSTEM_VERSION,
                market        = "crypto",
            )
            db.add(row)
            db.flush()
            db.refresh(row)
            log.info(
                "Signal saved id:%s %s %s grade:%s rr:%.2f",
                row.id, result.coin, result.direction, result.grade, result.rr1,
            )
            return row.id

    except Exception as e:
        log.error("save_signal %s: %s", result.coin, e)
        return None


def write_redis(coin: str, result: SignalResult, db_id: int) -> None:
    try:
        from redis_client import get_redis
        r = get_redis()
        if not r:
            return
        r.setex(f"signal:{coin}USDT", 1800, json.dumps({
            "coin":        coin,
            "grade":       result.grade,
            "direction":   result.direction,
            "entry":       result.entry,
            "sl":          result.sl,
            "stoploss":    result.sl,
            "tp1":         result.tp1,
            "tp":          result.tp1,
            "score":       result.score,
            "signal_id":   db_id,
            "valid_until": time.time() + 1800,
        }))
    except Exception as e:
        log.error("write_redis %s: %s", coin, e)


async def process_signal(result: SignalResult, db_id: int, session: str) -> None:
    try:
        from alerts.telegram import send_signal
        await send_signal(result.__dict__, result.coin, result.grade, session)

        from trade.executor import has_open_trade_or_position
        if await has_open_trade_or_position(result.coin):
            return

        from trade.executor import open_position
        await open_position(
            coin      = result.coin,
            direction = result.direction,
            entry     = result.entry,
            sl        = result.sl,
            tp        = result.tp1,
            stake     = result.stake,
            leverage  = result.leverage,
            signal_id = db_id,
            grade     = result.grade,
            score     = result.score,
            tp2       = result.tp2,
        )

    except Exception as e:
        log.error("process_signal %s: %s", result.coin, e)