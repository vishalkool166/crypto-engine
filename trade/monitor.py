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
_CACHE_TTL               = 2.0
_monitor_running:  bool  = False


def _get_open_trades_from_db() -> list:
    try:
        with get_session() as db:
            trades = db.query(TradeModel).filter(TradeModel.is_active == True).all()
            return [{
                "id":                 t.id,
                "coin":               t.coin,
                "direction":          t.direction,
                "grade":              t.grade,
                "entry_price":        t.entry_price,
                "sl_price":           t.sl_price,
                "tp1_price":          t.tp1_price,
                "position_size":      t.position_size,
                "margin_used":        t.margin_used,
                "leverage":           t.leverage,
                "sl_order_id":        t.sl_order_id,
                "tp1_order_id":       t.tp1_order_id,
                "opened_at": t.opened_at.replace(tzinfo=timezone.utc).isoformat() if t.opened_at else None,
                "signal_id":          t.signal_id,
                "regime_at_entry":    t.regime_at_entry,
                "session_at_entry":   t.session_at_entry,
                "score_at_entry":     t.score_at_entry,
                "entry_commission":   t.entry_commission,
                "entry_role":         t.entry_role,
                "funding_fees_paid":  t.funding_fees_paid,
                "total_commission":   t.total_commission,
                "slippage_entry_pct": t.slippage_entry_pct,
                "actual_fill_entry":  t.actual_fill_entry,
            } for t in trades]
    except Exception as e:
        log.error("_get_open_trades_from_db error: %s", e)
        return []


def _duration_str(opened_at: str | None, closed_at: datetime | None = None) -> str:
    if not opened_at:
        return "—"
    try:
        dt = datetime.fromisoformat(opened_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        end  = closed_at if closed_at else datetime.now(timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        diff = end - dt
        mins = int(diff.total_seconds() / 60)
        hrs  = mins // 60
        return f"{hrs}h {mins % 60}m" if hrs > 0 else f"{mins}m"
    except Exception:
        return "—"


def _live_pnl(
    entry:    float,
    price:    float,
    margin:   float,
    leverage: int,
    is_short: bool,
) -> tuple[float, float]:
    if not entry or not price or not margin:
        return 0.0, 0.0
    ratio = (entry - price) / entry if is_short else (price - entry) / entry
    return round(ratio * leverage, 4), round(ratio * margin * leverage, 4)


def _enrich_trade(trade: dict, position_map: dict) -> dict:
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

    unrealized = float(position.get("unRealizedProfit") or 0) if position else 0.0
    liquidation= float(position.get("liquidationPrice") or 0) if position else 0.0

    profit_ratio, profit_abs = _live_pnl(entry, live_price, margin, leverage, is_short)

    funding      = float(trade.get("funding_fees_paid") or 0)
    total_fee    = float(trade.get("total_commission")  or 0)
    entry_fee    = float(trade.get("entry_commission")  or 0)
    net_live     = round(profit_abs - total_fee - funding, 4)

    health = None
    try:
        from trade.health_monitor import get_health_from_redis
        health = get_health_from_redis(coin)
    except Exception:
        pass

    return {
        "trade_id":           trade["id"],
        "coin":               coin,
        "pair":               f"{coin}/USDT:USDT",
        "direction":          direction,
        "grade":              trade.get("grade", "--"),
        "is_short":           is_short,
        "is_open":            True,
        "entry_price":        entry,
        "actual_fill_entry":  float(trade.get("actual_fill_entry") or entry),
        "current_price":      live_price,
        "exit_price":         None,
        "actual_fill_exit":   None,
        "sl_price":           trade.get("sl_price"),
        "tp1_price":          trade.get("tp1_price"),
        "sl_signal":          trade.get("sl_price"),
        "tp1":                trade.get("tp1_price"),
        "position_size":      trade.get("position_size") or (margin * leverage),
        "margin_used":        margin,
        "leverage":           leverage,
        "profit_abs":         round(profit_abs, 4),
        "profit_ratio":       profit_ratio,
        "net_pnl_live":       net_live,
        "pnl":                None,
        "unrealized_pnl":     unrealized,
        "entry_commission":   entry_fee,
        "exit_commission":    0.0,
        "total_commission":   total_fee,
        "entry_role":         trade.get("entry_role", "taker"),
        "exit_role":          None,
        "funding_fees_paid":  funding,
        "slippage_entry_pct": float(trade.get("slippage_entry_pct") or 0),
        "slippage_exit_pct":  0.0,
        "realized_pnl":       0.0,
        "liquidation":        liquidation,
        "duration":           _duration_str(trade.get("opened_at")),
        "opened_at":          trade.get("opened_at"),
        "closed_at":          None,
        "outcome":            "pending",
        "close_reason":       None,
        "tp1_hit":            False,
        "health":             health,
        "regime_at_entry":    trade.get("regime_at_entry",  "--"),
        "session_at_entry":   trade.get("session_at_entry", "--"),
        "score_at_entry":     trade.get("score_at_entry",   0),
    }


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
        log.error("get_positions error: %s", e)
        positions = []

    position_map = {
        p.get("symbol", "").replace("USDT", ""): p
        for p in positions
    }

    enriched          = [_enrich_trade(t, position_map) for t in db_trades]
    _position_cache   = {t["trade_id"]: t for t in enriched}
    _cache_updated_at = now
    return enriched


def invalidate_position_cache() -> None:
    global _position_cache, _cache_updated_at
    _position_cache   = {}
    _cache_updated_at = 0.0


async def _update_funding_fees(db_trades: list) -> None:
    for trade in db_trades:
        trade_id  = trade["id"]
        coin      = trade["coin"]
        opened_at = trade.get("opened_at")
        if not opened_at:
            continue
        try:
            dt = datetime.fromisoformat(opened_at)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if (datetime.now(timezone.utc) - dt).total_seconds() / 3600 < 8:
                continue
            total = await get_funding_fees(f"{coin}USDT", int(dt.timestamp() * 1000))
            if total == 0.0:
                continue
            with get_session() as db:
                t = db.query(TradeModel).filter(TradeModel.id == trade_id).first()
                if t and abs(total - float(t.funding_fees_paid or 0)) > 0.000001:
                    t.funding_fees_paid = total
                    t.total_commission  = round(
                        float(t.entry_commission or 0) +
                        float(t.exit_commission  or 0) +
                        abs(total), 8
                    )
                    log.info("Funding updated: %s total:%.6f", coin, total)
        except Exception as e:
            log.error("_update_funding_fees %s: %s", coin, e)


def _determine_exit_reason(trade: dict, exit_price: float) -> str:
    entry    = float(trade.get("entry_price") or 0)
    sl       = float(trade.get("sl_price")    or 0)
    tp       = float(trade.get("tp1_price")   or 0)
    is_short = trade.get("direction", "LONG") == "SHORT"

    if not entry:
        return "exchange_closed"
    if sl and tp:
        return "sl_hit" if abs(exit_price - sl) < abs(exit_price - tp) else "tp_hit"
    if sl:
        return "sl_hit" if (is_short and exit_price >= sl * 0.99) or (not is_short and exit_price <= sl * 1.01) else "exchange_closed"
    if tp:
        return "tp_hit" if (is_short and exit_price <= tp * 1.01) or (not is_short and exit_price >= tp * 0.99) else "exchange_closed"
    return "exchange_closed"


async def _get_exit_price(coin: str, trade: dict) -> float:
    try:
        from trade.exchange import get_user_trades
        trades = await get_user_trades(f"{coin}USDT", limit=5)
        if trades:
            reduce_trades = [t for t in trades if t.get("reduceOnly") or float(t.get("realizedPnl", 0)) != 0]
            return float((reduce_trades or trades)[-1].get("price", 0))
    except Exception as e:
        log.error("_get_exit_price %s: %s", coin, e)
    try:
        from trade.ws import get_mark_price
        price = get_mark_price(coin)
        if price:
            return price
    except Exception:
        pass
    return float(trade.get("entry_price") or 0)


async def _detect_exchange_closed_trades(db_trades: list, positions: list) -> None:
    active_coins = {
        p.get("symbol", "").replace("USDT", "")
        for p in positions
        if float(p.get("positionAmt", 0)) != 0
    }

    for trade in db_trades:
        coin     = trade["coin"]
        trade_id = trade["id"]
        if coin in active_coins:
            continue

        log.info("Position closed on exchange: %s trade_id:%s", coin, trade_id)
        exit_price  = await _get_exit_price(coin, trade)
        exit_reason = _determine_exit_reason(trade, exit_price)

        from trade.executor import _calc_pnl, _mark_closed
        pnl = _calc_pnl(
            direction  = trade["direction"],
            entry      = float(trade.get("entry_price") or 0),
            exit_price = exit_price,
            margin     = float(trade.get("margin_used") or 0),
            leverage   = int(trade.get("leverage") or 1),
        )

        _mark_closed(trade_id, exit_price, pnl, exit_reason)
        invalidate_position_cache()

        from trade.health_monitor import clear_health_state
        clear_health_state(coin)

        pnl_str = f"+${pnl:.4f}" if pnl >= 0 else f"-${abs(pnl):.4f}"

        from alerts.telegram import send
        await send(
            f"{'✅' if pnl >= 0 else '❌'} *{coin} {trade['direction']} Closed*\n\n"
            f"Reason: `{exit_reason}`\n"
            f"Exit:   `${exit_price:.6f}`\n"
            f"PnL:    `{pnl_str}`"
        )

        from events import emit
        asyncio.create_task(emit("trade_closed", {
            "coin":      coin,
            "direction": trade["direction"],
            "pnl":       pnl,
            "reason":    exit_reason,
        }))


async def run_monitor_cycle() -> None:
    db_trades = _get_open_trades_from_db()
    if not db_trades:
        return
    try:
        positions = await get_positions()
    except Exception as e:
        log.error("Monitor positions fetch error: %s", e)
        return

    position_map      = {p.get("symbol", "").replace("USDT", ""): p for p in positions}
    enriched          = [_enrich_trade(t, position_map) for t in db_trades]
    _position_cache.update({t["trade_id"]: t for t in enriched})

    await _detect_exchange_closed_trades(db_trades, positions)
    await _update_funding_fees(db_trades)

    try:
        from trade.health_monitor import run_health_checks
        await run_health_checks()
    except Exception as e:
        log.error("Health check error: %s", e)


def get_profit_summary() -> dict:
    try:
        with get_session() as db:
            closed = db.query(TradeModel).filter(TradeModel.outcome.in_(["win", "loss"])).all()
        if not closed:
            return {
                "profit_all_coin": 0.0, "profit_all_percent": 0.0,
                "profit_closed_coin": 0.0, "winrate": 0.0,
                "trade_count": 0, "wins": 0, "losses": 0,
                "total_commission": 0.0, "total_funding_fees": 0.0,
                "best_pair": "--", "best_pair_profit_ratio": 0.0,
                "worst_pair": "--", "worst_pair_profit_ratio": 0.0,
            }

        total_pnl  = sum(float(t.net_pnl or t.pnl or 0) for t in closed)
        total_fee  = sum(float(t.total_commission  or 0) for t in closed)
        total_fund = sum(float(t.funding_fees_paid or 0) for t in closed)
        wins       = [t for t in closed if t.outcome == "win"]
        winrate    = len(wins) / len(closed)
        avg_margin = sum(float(t.margin_used or 0) for t in closed) / len(closed) or 1

        by_coin: dict = {}
        for t in closed:
            by_coin[t.coin] = by_coin.get(t.coin, 0.0) + float(t.net_pnl or t.pnl or 0)

        best  = max(by_coin, key=by_coin.get) if by_coin else "--"
        worst = min(by_coin, key=by_coin.get) if by_coin else "--"

        return {
            "profit_all_coin":         round(total_pnl, 4),
            "profit_all_percent":      round(total_pnl / avg_margin * 100, 2),
            "profit_closed_coin":      round(total_pnl, 4),
            "winrate":                 round(winrate, 4),
            "trade_count":             len(closed),
            "wins":                    len(wins),
            "losses":                  len(closed) - len(wins),
            "total_commission":        round(total_fee,  4),
            "total_funding_fees":      round(total_fund, 4),
            "best_pair":               best,
            "best_pair_profit_ratio":  round(by_coin.get(best,  0) / avg_margin, 4),
            "worst_pair":              worst,
            "worst_pair_profit_ratio": round(by_coin.get(worst, 0) / avg_margin, 4),
        }
    except Exception as e:
        log.error("get_profit_summary error: %s", e)
        return {}


def get_daily_breakdown(days: int = 7) -> list:
    try:
        result = []
        today  = date.today()
        with get_session() as db:
            for i in range(days):
                day   = today - timedelta(days=i)
                start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
                end   = start + timedelta(days=1)
                trades= db.query(TradeModel).filter(
                    TradeModel.closed_at >= start,
                    TradeModel.closed_at <  end,
                    TradeModel.outcome.in_(["win", "loss"])
                ).all()
                result.append({
                    "date":        day.isoformat(),
                    "profit_abs":  round(sum(float(t.net_pnl or t.pnl or 0) for t in trades), 4),
                    "profit_ratio":0.0,
                    "trade_count": len(trades),
                    "wins":        sum(1 for t in trades if t.outcome == "win"),
                    "losses":      sum(1 for t in trades if t.outcome == "loss"),
                    "commission":  round(sum(float(t.total_commission  or 0) for t in trades), 4),
                    "funding":     round(sum(float(t.funding_fees_paid or 0) for t in trades), 4),
                })
        return list(reversed(result))
    except Exception as e:
        log.error("get_daily_breakdown error: %s", e)
        return []


def get_performance_by_coin() -> list:
    try:
        with get_session() as db:
            closed = db.query(TradeModel).filter(TradeModel.outcome.in_(["win", "loss"])).all()
        by_coin: dict = {}
        for t in closed:
            if t.coin not in by_coin:
                by_coin[t.coin] = {"wins": 0, "losses": 0, "pnl": 0.0, "commission": 0.0, "funding": 0.0}
            by_coin[t.coin]["pnl"]        += float(t.net_pnl or t.pnl or 0)
            by_coin[t.coin]["commission"]  += float(t.total_commission  or 0)
            by_coin[t.coin]["funding"]     += float(t.funding_fees_paid or 0)
            by_coin[t.coin]["wins" if t.outcome == "win" else "losses"] += 1

        result = []
        for coin, d in by_coin.items():
            total = d["wins"] + d["losses"]
            wr    = d["wins"] / total if total > 0 else 0
            result.append({
                "pair":         f"{coin}/USDT:USDT",
                "coin":         coin,
                "wins":         d["wins"],
                "losses":       d["losses"],
                "profit_abs":   round(d["pnl"],        4),
                "profit_ratio": round(wr,               4),
                "win_rate":     round(wr * 100,         1),
                "commission":   round(d["commission"],  4),
                "funding":      round(d["funding"],     4),
            })
        result.sort(key=lambda x: x["profit_abs"], reverse=True)
        return result
    except Exception as e:
        log.error("get_performance_by_coin error: %s", e)
        return []


def get_trade_history(limit: int = 20, offset: int = 0) -> list:
    try:
        with get_session() as db:
            trades = db.query(TradeModel).order_by(
                TradeModel.opened_at.desc()
            ).offset(offset).limit(limit).all()
        return [{
            "trade_id":             t.id,
            "coin":                 t.coin,
            "pair":                 f"{t.coin}/USDT:USDT",
            "direction":            t.direction,
            "grade":                t.grade,
            "is_short":             t.direction == "SHORT",
            "is_open":              t.is_active,
            "entry_price":          t.entry_price,
            "actual_fill_entry":    t.actual_fill_entry,
            "exit_price":           t.exit_price,
            "actual_fill_exit":     t.actual_fill_exit,
            "sl_price":             t.sl_price,
            "tp1_price":            t.tp1_price,
            "leverage":             t.leverage,
            "margin_used":          t.margin_used,
            "position_size":        t.position_size or (float(t.margin_used or 0) * int(t.leverage or 1)),
            "pnl":                  round(float(t.net_pnl or t.pnl or 0), 4),
            "net_pnl_live":         None,
            "realized_pnl":         round(float(t.realized_pnl_exchange or 0), 4),
            "total_commission":     round(float(t.total_commission  or 0), 6),
            "funding_fees_paid":    round(float(t.funding_fees_paid or 0), 6),
            "entry_commission":     round(float(t.entry_commission  or 0), 6),
            "exit_commission":      round(float(t.exit_commission   or 0), 6),
            "entry_role":           t.entry_role,
            "exit_role":            t.exit_role,
            "slippage_entry_pct":   round(float(t.slippage_entry_pct or 0), 4),
            "slippage_exit_pct":    round(float(t.slippage_exit_pct  or 0), 4),
            "outcome":              t.outcome,
            "close_reason":         t.close_reason,
            "tp1_hit":              t.tp1_hit,
            "regime_at_entry":      t.regime_at_entry,
            "session_at_entry":     t.session_at_entry,
            "score_at_entry":       t.score_at_entry,
            "opened_at": t.opened_at.replace(tzinfo=timezone.utc).isoformat() if t.opened_at else None,
            "closed_at": t.closed_at.replace(tzinfo=timezone.utc).isoformat() if t.closed_at else None,
            "duration":             _duration_str(
                t.opened_at.replace(tzinfo=timezone.utc).isoformat() if t.opened_at else None,
                t.closed_at
            ),
        } for t in trades]
    except Exception as e:
        log.error("get_trade_history error: %s", e)
        return []


async def run_monitor_loop() -> None:
    global _monitor_running
    _monitor_running = True
    log.info("Trade monitor started")
    while _monitor_running:
        try:
            await run_monitor_cycle()
        except Exception as e:
            log.error("Monitor loop error: %s", e)
        await asyncio.sleep(30)


def stop_monitor() -> None:
    global _monitor_running
    _monitor_running = False
    log.info("Trade monitor stopped")


def is_monitor_running() -> bool:
    return _monitor_running