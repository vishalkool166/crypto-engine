import asyncio
import logging
import time
from datetime import datetime, timezone, timedelta, date
from database import get_session, Trade as TradeModel, Signal as SignalModel
from trade.exchange import get_positions, get_ticker_price, get_balance, get_funding_fees
from config import cfg

log = logging.getLogger(__name__)

_position_cache:   dict  = {}
_cache_updated_at: float = 0.0
_CACHE_TTL               = 15.0
_monitor_running:  bool  = False


def _get_open_trades_from_db() -> list:
    try:
        with get_session() as db:
            trades = db.query(TradeModel).filter(
                TradeModel.is_active == True
            ).all()
            return [{
                "id":                trade.id,
                "coin":              trade.coin,
                "direction":         trade.direction,
                "grade":             trade.grade,
                "entry_price":       trade.entry_price,
                "sl_price":          trade.sl_price,
                "tp1_price":         trade.tp1_price,
                "position_size":     trade.position_size,
                "margin_used":       trade.margin_used,
                "leverage":          trade.leverage,
                "sl_order_id":       trade.sl_order_id,
                "tp1_order_id":      trade.tp1_order_id,
                "opened_at":         trade.opened_at.isoformat() if trade.opened_at else None,
                "signal_id":         trade.signal_id,
                "regime_at_entry":   trade.regime_at_entry,
                "session_at_entry":  trade.session_at_entry,
                "score_at_entry":    trade.score_at_entry,
                "entry_commission":  trade.entry_commission,
                "funding_fees_paid": trade.funding_fees_paid,
                "total_commission":  trade.total_commission,
            } for trade in trades]
    except Exception as e:
        log.error(f"_get_open_trades_from_db error: {e}")
        return []


def _enrich_with_live_data(db_trades: list, positions: list) -> list:
    position_map = {}
    for p in positions:
        symbol = p.get("symbol", "")
        coin   = symbol.replace("USDT", "")
        position_map[coin] = p

    result = []
    for trade in db_trades:
        coin      = trade["coin"]
        position  = position_map.get(coin)
        entry     = float(trade.get("entry_price") or 0)
        direction = trade.get("direction", "LONG")
        leverage  = int(trade.get("leverage") or 1)
        margin    = float(trade.get("margin_used") or 0)
        is_short  = direction == "SHORT"

        try:
            from trade.ws import get_mark_price
            live_price = get_mark_price(coin)
        except Exception:
            live_price = 0.0

        if not live_price and position:
            live_price = float(position.get("markPrice") or position.get("entryPrice") or entry)

        if not live_price:
            live_price = entry

        if position:
            unrealized_pnl = float(position.get("unRealizedProfit") or 0)
            liquidation    = float(position.get("liquidationPrice") or 0)
        else:
            unrealized_pnl = 0.0
            liquidation    = 0.0

        if entry > 0 and live_price > 0:
            if is_short:
                profit_ratio = (entry - live_price) / entry
            else:
                profit_ratio = (live_price - entry) / entry
            profit_ratio_leveraged = profit_ratio * leverage
            profit_abs = profit_ratio * margin * leverage
        else:
            profit_ratio           = 0.0
            profit_ratio_leveraged = 0.0
            profit_abs             = 0.0

        funding_fees = float(trade.get("funding_fees_paid") or 0)
        total_comm   = float(trade.get("total_commission") or 0)
        net_pnl_live = round(profit_abs - total_comm - funding_fees, 4)

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
            "trade_id":          trade["id"],
            "coin":              coin,
            "pair":              f"{coin}/USDT:USDT",
            "direction":         direction,
            "grade":             trade.get("grade", "--"),
            "is_short":          is_short,
            "entry_price":       entry,
            "current_price":     live_price,
            "sl_price":          trade.get("sl_price"),
            "tp1_price":         trade.get("tp1_price"),
            "position_size":     trade.get("position_size"),
            "margin_used":       margin,
            "leverage":          leverage,
            "profit_abs":        round(profit_abs, 4),
            "profit_ratio":      round(profit_ratio_leveraged, 4),
            "net_pnl_live":      net_pnl_live,
            "funding_fees_paid": funding_fees,
            "total_commission":  total_comm,
            "liquidation":       liquidation,
            "duration":          duration_str,
            "opened_at":         opened_at,
            "health":            health,
            "tp1":               trade.get("tp1_price"),
            "sl_signal":         trade.get("sl_price"),
            "regime_at_entry":   trade.get("regime_at_entry", "--"),
            "session_at_entry":  trade.get("session_at_entry", "--"),
            "score_at_entry":    trade.get("score_at_entry", 0),
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


async def _update_funding_fees(db_trades: list):
    for trade in db_trades:
        trade_id  = trade["id"]
        coin      = trade["coin"]
        opened_at = trade.get("opened_at")

        if not opened_at:
            continue

        try:
            if isinstance(opened_at, str):
                opened_dt = datetime.fromisoformat(opened_at)
            else:
                opened_dt = opened_at
            if opened_dt.tzinfo is None:
                opened_dt = opened_dt.replace(tzinfo=timezone.utc)

            hours_open = (datetime.now(timezone.utc) - opened_dt).total_seconds() / 3600
            if hours_open < 8:
                continue

            start_time_ms = int(opened_dt.timestamp() * 1000)
            symbol        = f"{coin}USDT"

            funding_total = await get_funding_fees(symbol, start_time_ms)

            if funding_total == 0.0:
                continue

            with get_session() as db:
                t = db.query(TradeModel).filter(
                    TradeModel.id == trade_id
                ).first()
                if t:
                    current_funding = float(t.funding_fees_paid or 0)
                    if abs(funding_total - current_funding) > 0.000001:
                        t.funding_fees_paid = funding_total
                        entry_comm          = float(t.entry_commission or 0)
                        exit_comm           = float(t.exit_commission or 0)
                        t.total_commission  = round(entry_comm + exit_comm + abs(funding_total), 8)
                        log.info(
                            f"Funding fees updated: {coin} "
                            f"total:{funding_total:.6f} USDT"
                        )

        except Exception as e:
            log.error(f"_update_funding_fees error {coin}: {e}")


async def _detect_exchange_closed_trades(
    db_trades: list,
    positions: list,
):
    position_symbols = set()
    for p in positions:
        symbol = p.get("symbol", "")
        coin   = symbol.replace("USDT", "")
        if float(p.get("positionAmt", 0)) != 0:
            position_symbols.add(coin)

    for trade in db_trades:
        coin     = trade["coin"]
        trade_id = trade["id"]

        if coin not in position_symbols:
            log.info(
                f"Position closed on exchange: {coin} trade_id:{trade_id}"
            )

            exit_price = await _get_exit_price(coin, trade)
            direction  = trade["direction"]
            entry      = float(trade.get("entry_price") or 0)
            margin     = float(trade.get("margin_used") or 0)
            leverage   = int(trade.get("leverage") or 1)

            from trade.executor import _calculate_pnl, _mark_trade_closed
            pnl = _calculate_pnl(
                direction  = direction,
                entry      = entry,
                exit_price = exit_price,
                margin     = margin,
                leverage   = leverage,
            )

            exit_reason = _determine_exit_reason(trade, exit_price)
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


async def _get_exit_price(coin: str, trade: dict) -> float:
    try:
        from trade.exchange import get_user_trades
        symbol = f"{coin}USDT"
        trades = await get_user_trades(symbol, limit=5)
        if trades:
            reduce_trades = [
                t for t in trades
                if t.get("reduceOnly") or float(t.get("realizedPnl", 0)) != 0
            ]
            if reduce_trades:
                return float(reduce_trades[-1].get("price", 0))
            return float(trades[-1].get("price", 0))
    except Exception as e:
        log.error(f"_get_exit_price error {coin}: {e}")

    try:
        from trade.ws import get_mark_price
        price = get_mark_price(coin)
        if price:
            return price
    except Exception:
        pass

    return float(trade.get("entry_price") or 0)


def _determine_exit_reason(trade: dict, exit_price: float) -> str:
    entry     = float(trade.get("entry_price") or 0)
    sl        = float(trade.get("sl_price")    or 0)
    tp        = float(trade.get("tp1_price")   or 0)
    direction = trade.get("direction", "LONG")
    is_short  = direction == "SHORT"

    if not entry:
        return "exchange_closed"

    if sl and tp:
        dist_sl = abs(exit_price - sl)
        dist_tp = abs(exit_price - tp)
        if dist_sl < dist_tp:
            return "sl_hit"
        else:
            return "tp_hit"

    if sl:
        if is_short and exit_price >= sl * 0.99:
            return "sl_hit"
        if not is_short and exit_price <= sl * 1.01:
            return "sl_hit"

    if tp:
        if is_short and exit_price <= tp * 1.01:
            return "tp_hit"
        if not is_short and exit_price >= tp * 0.99:
            return "tp_hit"

    return "exchange_closed"


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

    await _detect_exchange_closed_trades(db_trades, positions)

    await _update_funding_fees(db_trades)

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
                    "profit_all_coin":         0.0,
                    "profit_all_percent":      0.0,
                    "profit_closed_coin":      0.0,
                    "winrate":                 0.0,
                    "trade_count":             0,
                    "wins":                    0,
                    "losses":                  0,
                    "total_commission":        0.0,
                    "total_funding_fees":      0.0,
                    "best_pair":               "--",
                    "best_pair_profit_ratio":  0.0,
                    "worst_pair":              "--",
                    "worst_pair_profit_ratio": 0.0,
                }

            total_pnl        = sum(float(t.net_pnl or t.pnl or 0) for t in closed)
            total_commission = sum(float(t.total_commission or 0) for t in closed)
            total_funding    = sum(float(t.funding_fees_paid or 0) for t in closed)
            wins             = [t for t in closed if t.outcome == "win"]
            winrate          = len(wins) / len(closed) if closed else 0

            by_coin = {}
            for t in closed:
                if t.coin not in by_coin:
                    by_coin[t.coin] = 0.0
                by_coin[t.coin] += float(t.net_pnl or t.pnl or 0)

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
                "total_commission":        round(total_commission, 4),
                "total_funding_fees":      round(total_funding, 4),
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
                day_start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
                day_end   = day_start + timedelta(days=1)

                trades = db.query(TradeModel).filter(
                    TradeModel.closed_at  >= day_start,
                    TradeModel.closed_at  <  day_end,
                    TradeModel.outcome.in_(["win", "loss"])
                ).all()

                day_pnl        = sum(float(t.net_pnl or t.pnl or 0) for t in trades)
                day_commission = sum(float(t.total_commission or 0) for t in trades)
                day_funding    = sum(float(t.funding_fees_paid or 0) for t in trades)
                day_wins       = sum(1 for t in trades if t.outcome == "win")
                day_losses     = sum(1 for t in trades if t.outcome == "loss")

                result.append({
                    "date":        day.isoformat(),
                    "profit_abs":  round(day_pnl, 4),
                    "profit_ratio":0.0,
                    "trade_count": len(trades),
                    "wins":        day_wins,
                    "losses":      day_losses,
                    "commission":  round(day_commission, 4),
                    "funding":     round(day_funding, 4),
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
                        "coin":       t.coin,
                        "wins":       0,
                        "losses":     0,
                        "pnl":        0.0,
                        "commission": 0.0,
                        "funding":    0.0,
                    }
                by_coin[t.coin]["pnl"]        += float(t.net_pnl or t.pnl or 0)
                by_coin[t.coin]["commission"]  += float(t.total_commission or 0)
                by_coin[t.coin]["funding"]     += float(t.funding_fees_paid or 0)
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
                    "commission":   round(data["commission"], 4),
                    "funding":      round(data["funding"], 4),
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
                "trade_id":             t.id,
                "coin":                 t.coin,
                "pair":                 f"{t.coin}/USDT:USDT",
                "direction":            t.direction,
                "grade":                t.grade,
                "is_short":             t.direction == "SHORT",
                "entry_price":          t.entry_price,
                "actual_fill_entry":    t.actual_fill_entry,
                "exit_price":           t.exit_price,
                "actual_fill_exit":     t.actual_fill_exit,
                "sl_price":             t.sl_price,
                "tp1_price":            t.tp1_price,
                "leverage":             t.leverage,
                "margin_used":          t.margin_used,
                "pnl":                  round(float(t.net_pnl or t.pnl or 0), 4),
                "realized_pnl":         round(float(t.realized_pnl_exchange or 0), 4),
                "total_commission":     round(float(t.total_commission or 0), 6),
                "funding_fees_paid":    round(float(t.funding_fees_paid or 0), 6),
                "entry_role":           t.entry_role,
                "exit_role":            t.exit_role,
                "slippage_entry_pct":   round(float(t.slippage_entry_pct or 0), 4),
                "slippage_exit_pct":    round(float(t.slippage_exit_pct or 0), 4),
                "outcome":              t.outcome,
                "close_reason":         t.close_reason,
                "tp1_hit":              t.tp1_hit,
                "regime_at_entry":      t.regime_at_entry,
                "session_at_entry":     t.session_at_entry,
                "score_at_entry":       t.score_at_entry,
                "opened_at":            t.opened_at.isoformat()  if t.opened_at  else None,
                "closed_at":            t.closed_at.isoformat()  if t.closed_at  else None,
                "is_open":              t.is_active,
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