import asyncio
import logging
import time
from datetime import datetime, timezone, timedelta, date
from database import get_session, Trade as TradeModel, Signal as SignalModel
from trade.exchange import get_exchange, get_positions, get_ticker_price
from config import cfg

log = logging.getLogger(__name__)

_position_cache:     dict  = {}
_cache_updated_at:   float = 0.0
_CACHE_TTL                 = 15.0

_monitor_running:    bool  = False


def _get_open_trades_from_db() -> list:
    try:
        with get_session() as db:
            trades = db.query(TradeModel).filter(
                TradeModel.is_active == True
            ).all()
            return [{
                "id":            t.id,
                "coin":          t.coin,
                "direction":     t.direction,
                "grade":         t.grade,
                "entry_price":   t.entry_price,
                "sl_price":      t.sl_price,
                "tp1_price":     t.tp1_price,
                "position_size": t.position_size,
                "margin_used":   t.margin_used,
                "leverage":      t.leverage,
                "sl_order_id":   t.sl_order_id,
                "tp1_order_id":  t.tp1_order_id,
                "opened_at":     t.opened_at.isoformat() if t.opened_at else None,
                "signal_id":     t.signal_id,
            } for t in trades]
    except Exception as e:
        log.error(f"_get_open_trades_from_db error: {e}")
        return []


def _enrich_with_live_data(db_trades: list, positions: list) -> list:
    position_map = {}
    for p in positions:
        symbol = p.get("symbol", "")
        coin   = symbol.replace("/USDT:USDT", "").replace("/USDT", "")
        position_map[coin] = p

    result = []
    for trade in db_trades:
        coin     = trade["coin"]
        position = position_map.get(coin)

        entry        = float(trade.get("entry_price") or 0)
        direction    = trade.get("direction", "LONG")
        leverage     = int(trade.get("leverage") or 1)
        margin       = float(trade.get("margin_used") or 0)
        is_short     = direction == "SHORT"

        if position:
            current_price  = float(position.get("markPrice")    or position.get("entryPrice") or entry)
            unrealized_pnl = float(position.get("unrealizedPnl") or 0)
            liquidation    = float(position.get("liquidationPrice") or 0)
        else:
            current_price  = entry
            unrealized_pnl = 0.0
            liquidation    = 0.0

        if entry > 0:
            if is_short:
                profit_ratio = (entry - current_price) / entry
            else:
                profit_ratio = (current_price - entry) / entry
            profit_ratio_leveraged = profit_ratio * leverage
        else:
            profit_ratio           = 0.0
            profit_ratio_leveraged = 0.0

        opened_at    = trade.get("opened_at")
        duration_str = "--"
        if opened_at:
            try:
                if isinstance(opened_at, str):
                    opened_dt = datetime.fromisoformat(opened_at)
                else:
                    opened_dt = opened_at
                if opened_dt.tzinfo is None:
                    opened_dt = opened_dt.replace(tzinfo=timezone.utc)
                diff     = datetime.now(timezone.utc) - opened_dt
                mins     = int(diff.total_seconds() / 60)
                hrs      = mins // 60
                rem_mins = mins % 60
                duration_str = f"{hrs}h {rem_mins}m" if hrs > 0 else f"{mins}m"
            except Exception:
                pass

        health = None
        try:
            from trade.health_monitor import get_health_from_redis
            health = get_health_from_redis(coin)
        except Exception:
            pass

        result.append({
            "trade_id":      trade["id"],
            "coin":          coin,
            "pair":          f"{coin}/USDT:USDT",
            "direction":     direction,
            "grade":         trade.get("grade", "--"),
            "is_short":      is_short,
            "entry_price":   entry,
            "current_price": current_price,
            "sl_price":      trade.get("sl_price"),
            "tp1_price":     trade.get("tp1_price"),
            "position_size": trade.get("position_size"),
            "margin_used":   margin,
            "leverage":      leverage,
            "profit_abs":    round(unrealized_pnl, 4),
            "profit_ratio":  round(profit_ratio_leveraged, 4),
            "liquidation":   liquidation,
            "duration":      duration_str,
            "opened_at":     opened_at,
            "health":        health,
            "tp1":           trade.get("tp1_price"),
            "sl_signal":     trade.get("sl_price"),
        })

    return result


async def get_open_positions_enriched() -> list:
    global _position_cache, _cache_updated_at

    now = time.time()
    if _position_cache and (now - _cache_updated_at) < _CACHE_TTL:
        return list(_position_cache.values())

    db_trades = _get_open_trades_from_db()
    if not db_trades:
        _position_cache   = {}
        _cache_updated_at = now
        return []

    try:
        positions = await get_positions()
    except Exception as e:
        log.error(f"get_positions error: {e}")
        positions = []

    enriched = _enrich_with_live_data(db_trades, positions)

    _position_cache   = {t["trade_id"]: t for t in enriched}
    _cache_updated_at = now

    return enriched


def invalidate_position_cache():
    global _position_cache, _cache_updated_at
    _position_cache   = {}
    _cache_updated_at = 0.0


async def _check_sl_tp_hit(trade: dict) -> tuple[bool, str, float]:
    coin      = trade["coin"]
    symbol    = f"{coin}/USDT:USDT"
    is_short  = trade["is_short"]
    sl        = float(trade.get("sl_price")  or 0)
    tp        = float(trade.get("tp1_price") or 0)

    if not sl or not tp:
        return False, "", 0.0

    try:
        current_price = await get_ticker_price(symbol)
        if not current_price:
            return False, "", 0.0

        if is_short:
            if current_price >= sl:
                return True, "sl_hit", current_price
            if current_price <= tp:
                return True, "tp_hit", current_price
        else:
            if current_price <= sl:
                return True, "sl_hit", current_price
            if current_price >= tp:
                return True, "tp_hit", current_price

        return False, "", current_price

    except Exception as e:
        log.error(f"_check_sl_tp_hit error {coin}: {e}")
        return False, "", 0.0


async def _verify_position_closed_on_exchange(coin: str) -> bool:
    try:
        symbol    = f"{coin}/USDT:USDT"
        positions = await get_positions()
        for p in positions:
            sym = p.get("symbol", "")
            c   = sym.replace("/USDT:USDT", "").replace("/USDT", "")
            if c == coin and float(p.get("contracts", 0)) > 0:
                return False
        return True
    except Exception as e:
        log.error(f"_verify_position_closed_on_exchange error {coin}: {e}")
        return False


async def _handle_closed_trade(
    trade:       dict,
    exit_reason: str,
    exit_price:  float,
):
    from trade.executor import _mark_trade_closed, _calculate_pnl

    trade_id  = trade["trade_id"]
    coin      = trade["coin"]
    direction = trade["direction"]
    entry     = float(trade.get("entry_price") or 0)
    margin    = float(trade.get("margin_used") or 0)
    leverage  = int(trade.get("leverage") or 1)

    pnl = _calculate_pnl(
        direction  = direction,
        entry      = entry,
        exit_price = exit_price,
        position   = margin,
        leverage   = leverage,
    )

    _mark_trade_closed(trade_id, exit_price, pnl, exit_reason)
    invalidate_position_cache()

    from trade.health_monitor import clear_health_state
    clear_health_state(coin)

    emoji   = "✅" if pnl >= 0 else "❌"
    pnl_str = f"+${pnl:.4f}" if pnl >= 0 else f"-${abs(pnl):.4f}"

    from alerts.telegram import send
    await send(
        f"{emoji} *{coin} {direction} Closed*\n\n"
        f"Reason: `{exit_reason}`\n"
        f"Exit:   `${exit_price:.6f}`\n"
        f"PnL:    `{pnl_str}`"
    )

    from events import emit
    asyncio.create_task(emit("trade_closed", {
        "coin":      coin,
        "direction": direction,
        "pnl":       pnl,
        "reason":    exit_reason,
    }))

    log.info(
        f"Trade closed: {coin} {direction} "
        f"exit:{exit_price} pnl:{pnl} reason:{exit_reason}"
    )


async def run_monitor_cycle():
    db_trades = _get_open_trades_from_db()
    if not db_trades:
        return

    try:
        positions = await get_positions()
    except Exception as e:
        log.error(f"Monitor positions fetch error: {e}")
        return

    enriched = _enrich_with_live_data(db_trades, positions)

    _position_cache.update({t["trade_id"]: t for t in enriched})

    for trade in enriched:
        coin     = trade["coin"]
        trade_id = trade["trade_id"]

        try:
            hit, reason, exit_price = await _check_sl_tp_hit(trade)

            if hit:
                log.info(f"Exit detected: {coin} reason:{reason} price:{exit_price}")

                confirmed = await _verify_position_closed_on_exchange(coin)

                if confirmed:
                    await _handle_closed_trade(trade, reason, exit_price)
                else:
                    log.warning(
                        f"Exit detected for {coin} but position still open on exchange "
                        f"— exchange order may still be working"
                    )

        except Exception as e:
            log.error(f"Monitor cycle error for {coin} trade_id:{trade_id}: {e}")

    try:
        from trade.health_monitor import run_health_checks
        await run_health_checks()
    except Exception as e:
        log.error(f"Health check error in monitor: {e}")


def get_profit_summary() -> dict:
    try:
        with get_session() as db:
            closed = db.query(TradeModel).filter(
                TradeModel.outcome.in_(["win", "loss"])
            ).all()

            if not closed:
                return {
                    "profit_all_coin":        0.0,
                    "profit_all_percent":     0.0,
                    "profit_closed_coin":     0.0,
                    "winrate":                0.0,
                    "trade_count":            0,
                    "wins":                   0,
                    "losses":                 0,
                    "best_pair":              "--",
                    "best_pair_profit_ratio": 0.0,
                    "worst_pair":             "--",
                    "worst_pair_profit_ratio":0.0,
                }

            total_pnl = sum(float(t.pnl or 0) for t in closed)
            wins      = [t for t in closed if t.outcome == "win"]
            winrate   = len(wins) / len(closed) if closed else 0

            by_coin = {}
            for t in closed:
                if t.coin not in by_coin:
                    by_coin[t.coin] = 0.0
                by_coin[t.coin] += float(t.pnl or 0)

            best_coin  = max(by_coin, key=by_coin.get) if by_coin else "--"
            worst_coin = min(by_coin, key=by_coin.get) if by_coin else "--"

            avg_margin = sum(
                float(t.margin_used or 0) for t in closed
            ) / len(closed) if closed else 1

            return {
                "profit_all_coin":         round(total_pnl, 4),
                "profit_all_percent":      round(total_pnl / avg_margin * 100, 2) if avg_margin else 0,
                "profit_closed_coin":      round(total_pnl, 4),
                "winrate":                 round(winrate, 4),
                "trade_count":             len(closed),
                "wins":                    len(wins),
                "losses":                  len(closed) - len(wins),
                "best_pair":               best_coin,
                "best_pair_profit_ratio":  round(by_coin.get(best_coin, 0) / avg_margin, 4) if avg_margin else 0,
                "worst_pair":              worst_coin,
                "worst_pair_profit_ratio": round(by_coin.get(worst_coin, 0) / avg_margin, 4) if avg_margin else 0,
            }

    except Exception as e:
        log.error(f"get_profit_summary error: {e}")
        return {}


def get_daily_breakdown(days: int = 7) -> list:
    try:
        result = []
        today  = date.today()

        with get_session() as db:
            for i in range(days):
                day       = today - timedelta(days=i)
                day_str   = day.isoformat()
                day_start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
                day_end   = day_start + timedelta(days=1)

                trades = db.query(TradeModel).filter(
                    TradeModel.closed_at  >= day_start,
                    TradeModel.closed_at  <  day_end,
                    TradeModel.outcome.in_(["win", "loss"])
                ).all()

                day_pnl    = sum(float(t.pnl or 0) for t in trades)
                day_wins   = sum(1 for t in trades if t.outcome == "win")
                day_losses = sum(1 for t in trades if t.outcome == "loss")

                result.append({
                    "date":          day_str,
                    "profit_abs":    round(day_pnl, 4),
                    "profit_ratio":  0.0,
                    "trade_count":   len(trades),
                    "wins":          day_wins,
                    "losses":        day_losses,
                })

        return result

    except Exception as e:
        log.error(f"get_daily_breakdown error: {e}")
        return []


def get_performance_by_coin() -> list:
    try:
        with get_session() as db:
            closed = db.query(TradeModel).filter(
                TradeModel.outcome.in_(["win", "loss"])
            ).all()

            by_coin = {}
            for t in closed:
                if t.coin not in by_coin:
                    by_coin[t.coin] = {
                        "coin":   t.coin,
                        "wins":   0,
                        "losses": 0,
                        "pnl":    0.0,
                    }
                by_coin[t.coin]["pnl"] += float(t.pnl or 0)
                if t.outcome == "win":
                    by_coin[t.coin]["wins"]   += 1
                else:
                    by_coin[t.coin]["losses"] += 1

            result = []
            for coin, data in by_coin.items():
                total    = data["wins"] + data["losses"]
                win_rate = data["wins"] / total if total > 0 else 0
                result.append({
                    "pair":         f"{coin}/USDT:USDT",
                    "coin":         coin,
                    "wins":         data["wins"],
                    "losses":       data["losses"],
                    "profit_abs":   round(data["pnl"], 4),
                    "profit_ratio": round(win_rate, 4),
                    "win_rate":     round(win_rate * 100, 1),
                })

            result.sort(key=lambda x: x["profit_abs"], reverse=True)
            return result

    except Exception as e:
        log.error(f"get_performance_by_coin error: {e}")
        return []


def get_trade_history(limit: int = 50) -> list:
    try:
        with get_session() as db:
            trades = db.query(TradeModel).order_by(
                TradeModel.opened_at.desc()
            ).limit(limit).all()

            return [{
                "trade_id":    t.id,
                "coin":        t.coin,
                "pair":        f"{t.coin}/USDT:USDT",
                "direction":   t.direction,
                "grade":       t.grade,
                "is_short":    t.direction == "SHORT",
                "entry_price": t.entry_price,
                "exit_price":  t.exit_price,
                "sl_price":    t.sl_price,
                "tp1_price":   t.tp1_price,
                "leverage":    t.leverage,
                "margin_used": t.margin_used,
                "pnl":         round(float(t.pnl or 0), 4),
                "outcome":     t.outcome,
                "close_reason":t.close_reason,
                "opened_at":   t.opened_at.isoformat()  if t.opened_at  else None,
                "closed_at":   t.closed_at.isoformat()  if t.closed_at  else None,
                "is_open":     t.is_active,
            } for t in trades]

    except Exception as e:
        log.error(f"get_trade_history error: {e}")
        return []


async def run_monitor_loop():
    global _monitor_running
    _monitor_running = True
    log.info("Trade monitor started")

    while _monitor_running:
        try:
            await run_monitor_cycle()
        except Exception as e:
            log.error(f"Monitor loop error: {e}")
        await asyncio.sleep(30)


def stop_monitor():
    global _monitor_running
    _monitor_running = False
    log.info("Trade monitor stopped")


def is_monitor_running() -> bool:
    return _monitor_running