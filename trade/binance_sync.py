import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from database import get_session, BinanceTradeRecord, BinanceFundingRecord, BinanceAccountSnapshot, Trade as TradeModel

log = logging.getLogger(__name__)


async def sync_trade_open(
    trade_id:       int,
    coin:           str,
    direction:      str,
    entry_order_id: str,
    fill_price:     float,
    filled_qty:     float,
    commission:     float,
    commission_asset: str,
    entry_role:     str,
    realized_pnl:   float,
    raw_order_json: dict,
) -> None:
    try:
        position_data = await _fetch_position(coin)
        account_data  = await _fetch_account()

        liq_price    = 0.0
        mark_price   = 0.0
        margin_type  = "isolated"
        pos_margin   = 0.0
        leverage     = 0

        if position_data:
            liq_price   = float(position_data.get("liquidationPrice", 0) or 0)
            mark_price  = float(position_data.get("markPrice",         0) or 0)
            margin_type = position_data.get("marginType", "isolated")
            pos_margin  = float(position_data.get("isolatedMargin",    0) or 0)
            leverage    = int(position_data.get("leverage",            0) or 0)

        wallet_balance = 0.0
        available      = 0.0
        unrealized     = 0.0

        if account_data:
            for asset in account_data.get("assets", []):
                if asset.get("asset") == "USDT":
                    wallet_balance = float(asset.get("walletBalance",     0) or 0)
                    available      = float(asset.get("availableBalance",  0) or 0)
                    unrealized     = float(asset.get("unrealizedProfit",  0) or 0)
                    break

        with get_session() as db:
            existing = db.query(BinanceTradeRecord).filter(
                BinanceTradeRecord.trade_id == trade_id
            ).first()

            if existing:
                existing.entry_order_id         = entry_order_id
                existing.entry_avg_price        = fill_price
                existing.entry_filled_qty       = filled_qty
                existing.entry_commission       = commission
                existing.entry_commission_asset = commission_asset
                existing.entry_role             = entry_role
                existing.entry_realized_pnl     = realized_pnl
                existing.leverage               = leverage
                existing.margin_type            = margin_type
                existing.position_margin        = pos_margin
                existing.liquidation_price      = liq_price
                existing.mark_price_at_entry    = mark_price
                existing.wallet_balance_at_open = wallet_balance
                existing.available_at_open      = available
                existing.unrealized_pnl_at_open = unrealized
                existing.raw_entry_order_json   = json.dumps(raw_order_json)
                existing.raw_position_json      = json.dumps(position_data or {})
                existing.raw_account_json       = json.dumps(account_data  or {})
                existing.synced_at              = datetime.now(timezone.utc)
            else:
                record = BinanceTradeRecord(
                    trade_id                = trade_id,
                    coin                    = coin,
                    symbol                  = f"{coin}USDT",
                    direction               = direction,
                    entry_order_id          = entry_order_id,
                    entry_avg_price         = fill_price,
                    entry_filled_qty        = filled_qty,
                    entry_commission        = commission,
                    entry_commission_asset  = commission_asset,
                    entry_role              = entry_role,
                    entry_realized_pnl      = realized_pnl,
                    leverage                = leverage,
                    margin_type             = margin_type,
                    position_margin         = pos_margin,
                    liquidation_price       = liq_price,
                    mark_price_at_entry     = mark_price,
                    wallet_balance_at_open  = wallet_balance,
                    available_at_open       = available,
                    unrealized_pnl_at_open  = unrealized,
                    raw_entry_order_json    = json.dumps(raw_order_json),
                    raw_position_json       = json.dumps(position_data or {}),
                    raw_account_json        = json.dumps(account_data  or {}),
                    synced_at               = datetime.now(timezone.utc),
                )
                db.add(record)

        await _snapshot_account(trigger="trade_open", trade_id=trade_id)

        _update_trade_binance_fields(
            trade_id         = trade_id,
            entry_price      = fill_price,
            fill_qty         = filled_qty,
            leverage         = leverage,
            margin_type      = margin_type,
            liq_price        = liq_price,
            mark_price_entry = mark_price,
            wallet_at_open   = wallet_balance,
        )

        log.info(
            "Binance sync open: trade_id=%s %s liq:%.4f mark:%.4f wallet:%.2f",
            trade_id, coin, liq_price, mark_price, wallet_balance
        )

    except Exception as e:
        log.error("sync_trade_open trade_id=%s: %s", trade_id, e)


async def sync_trade_close(
    trade_id:        int,
    coin:            str,
    direction:       str,
    exit_order_id:   str,
    exit_price:      float,
    exit_qty:        float,
    exit_commission: float,
    exit_role:       str,
    realized_pnl:    float,
    raw_order_json:  dict,
) -> None:
    try:
        account_data = await _fetch_account()

        wallet_balance  = 0.0
        available       = 0.0

        if account_data:
            for asset in account_data.get("assets", []):
                if asset.get("asset") == "USDT":
                    wallet_balance = float(asset.get("walletBalance",    0) or 0)
                    available      = float(asset.get("availableBalance", 0) or 0)
                    break

        from trade.ws import get_mark_price
        mark_price_exit = get_mark_price(coin) or exit_price

        with get_session() as db:
            record = db.query(BinanceTradeRecord).filter(
                BinanceTradeRecord.trade_id == trade_id
            ).first()

            if not record:
                record = BinanceTradeRecord(
                    trade_id  = trade_id,
                    coin      = coin,
                    symbol    = f"{coin}USDT",
                    direction = direction,
                )
                db.add(record)

            record.exit_order_id          = exit_order_id
            record.exit_avg_price         = exit_price
            record.exit_filled_qty        = exit_qty
            record.exit_commission        = exit_commission
            record.exit_role              = exit_role
            record.exit_realized_pnl      = realized_pnl
            record.mark_price_at_exit     = mark_price_exit
            record.wallet_balance_at_close= wallet_balance
            record.available_at_close     = available
            record.raw_exit_order_json    = json.dumps(raw_order_json)
            record.raw_account_json       = json.dumps(account_data or {})
            record.synced_at              = datetime.now(timezone.utc)

            entry_commission = float(record.entry_commission or 0)
            total_commission = round(entry_commission + exit_commission, 8)
            gross_pnl        = realized_pnl
            net_pnl          = round(gross_pnl - exit_commission, 8)

            record.total_commission  = total_commission
            record.gross_realized_pnl= gross_pnl

        await _fetch_and_store_income(trade_id, coin)
        await _snapshot_account(trigger="trade_close", trade_id=trade_id)

        with get_session() as db:
            record = db.query(BinanceTradeRecord).filter(
                BinanceTradeRecord.trade_id == trade_id
            ).first()
            if record:
                funding_total = float(record.total_funding or 0)
                net_pnl_final = round(
                    float(record.gross_realized_pnl or 0) -
                    float(record.total_commission   or 0) -
                    abs(funding_total),
                    8
                )
                record.net_pnl          = net_pnl_final
                record.income_fetched   = True

                _update_trade_binance_close(
                    trade_id         = trade_id,
                    exit_price       = exit_price,
                    realized_pnl     = float(record.gross_realized_pnl or 0),
                    commission_total = float(record.total_commission    or 0),
                    funding_total    = funding_total,
                    net_pnl          = net_pnl_final,
                    wallet_at_close  = wallet_balance,
                )

        log.info(
            "Binance sync close: trade_id=%s %s realized:%.4f commission:%.4f net:%.4f",
            trade_id, coin,
            realized_pnl,
            total_commission,
            net_pnl,
        )

    except Exception as e:
        log.error("sync_trade_close trade_id=%s: %s", trade_id, e)


async def _fetch_and_store_income(trade_id: int, coin: str) -> None:
    try:
        from trade.exchange import _get, _signed
        from database import SessionLocal

        with SessionLocal() as db:
            trade = db.query(TradeModel).filter(TradeModel.id == trade_id).first()
            if not trade or not trade.opened_at:
                return
            opened_at = trade.opened_at
            closed_at = trade.closed_at or datetime.now(timezone.utc)

        if opened_at.tzinfo is None:
            opened_at = opened_at.replace(tzinfo=timezone.utc)
        if closed_at.tzinfo is None:
            closed_at = closed_at.replace(tzinfo=timezone.utc)

        start_ms = int(opened_at.timestamp() * 1000) - 60000
        end_ms   = int(closed_at.timestamp() * 1000) + 60000
        symbol   = f"{coin}USDT"

        income_types = ["REALIZED_PNL", "COMMISSION", "FUNDING_FEE"]
        all_income   = []

        for income_type in income_types:
            try:
                data = await _get("/fapi/v1/income", {
                    "symbol":     symbol,
                    "incomeType": income_type,
                    "startTime":  start_ms,
                    "endTime":    end_ms,
                    "limit":      100,
                }, signed=True)
                if isinstance(data, list):
                    all_income.extend(data)
            except Exception as e:
                log.warning("Income fetch %s %s: %s", income_type, coin, e)

        if not all_income:
            return

        total_realized  = 0.0
        total_commission= 0.0
        total_funding   = 0.0

        for item in all_income:
            income_type = item.get("incomeType", "")
            amount      = float(item.get("income", 0) or 0)

            if income_type == "REALIZED_PNL":
                total_realized += amount
            elif income_type == "COMMISSION":
                total_commission += abs(amount)
            elif income_type == "FUNDING_FEE":
                total_funding += amount

                funding_time = datetime.fromtimestamp(
                    int(item.get("time", 0)) / 1000,
                    tz=timezone.utc
                )

                with get_session() as db:
                    existing = db.query(BinanceFundingRecord).filter(
                        BinanceFundingRecord.symbol       == symbol,
                        BinanceFundingRecord.funding_time == funding_time,
                    ).first()

                    if not existing:
                        db.add(BinanceFundingRecord(
                            trade_id        = trade_id,
                            coin            = coin,
                            symbol          = symbol,
                            funding_time    = funding_time,
                            funding_fee     = amount,
                            raw_income_json = json.dumps(item),
                        ))

        with get_session() as db:
            record = db.query(BinanceTradeRecord).filter(
                BinanceTradeRecord.trade_id == trade_id
            ).first()
            if record:
                record.gross_realized_pnl = total_realized  if total_realized  != 0 else record.gross_realized_pnl
                record.total_commission   = total_commission if total_commission != 0 else record.total_commission
                record.total_funding      = total_funding
                record.raw_income_json    = json.dumps(all_income)
                record.income_fetched     = True

        log.info(
            "Income fetched: trade_id=%s realized:%.4f commission:%.4f funding:%.4f",
            trade_id, total_realized, total_commission, total_funding
        )

    except Exception as e:
        log.error("_fetch_and_store_income trade_id=%s: %s", trade_id, e)


async def _fetch_position(coin: str) -> dict | None:
    try:
        from trade.exchange import _get
        data = await _get("/fapi/v2/positionRisk", {"symbol": f"{coin}USDT"}, signed=True)
        if isinstance(data, list) and data:
            return data[0]
        return None
    except Exception as e:
        log.warning("_fetch_position %s: %s", coin, e)
        return None


async def _fetch_account() -> dict | None:
    try:
        from trade.exchange import _get
        return await _get("/fapi/v2/account", signed=True)
    except Exception as e:
        log.warning("_fetch_account: %s", e)
        return None


async def _snapshot_account(trigger: str, trade_id: int = None) -> None:
    try:
        account_data = await _fetch_account()
        if not account_data:
            return

        wallet_balance = 0.0
        available      = 0.0
        unrealized     = 0.0

        for asset in account_data.get("assets", []):
            if asset.get("asset") == "USDT":
                wallet_balance = float(asset.get("walletBalance",    0) or 0)
                available      = float(asset.get("availableBalance", 0) or 0)
                unrealized     = float(asset.get("unrealizedProfit", 0) or 0)
                break

        positions = [
            p for p in account_data.get("positions", [])
            if float(p.get("positionAmt", 0)) != 0
        ]

        with get_session() as db:
            db.add(BinanceAccountSnapshot(
                trigger              = trigger,
                trade_id             = trade_id,
                wallet_balance       = wallet_balance,
                available_balance    = available,
                total_unrealized_pnl = unrealized,
                total_position_count = len(positions),
                positions_json       = json.dumps(positions),
                raw_account_json     = json.dumps(account_data),
            ))

    except Exception as e:
        log.error("_snapshot_account: %s", e)


def _update_trade_binance_fields(
    trade_id:         int,
    entry_price:      float,
    fill_qty:         float,
    leverage:         int,
    margin_type:      str,
    liq_price:        float,
    mark_price_entry: float,
    wallet_at_open:   float,
) -> None:
    try:
        with get_session() as db:
            trade = db.query(TradeModel).filter(TradeModel.id == trade_id).first()
            if trade:
                trade.binance_entry_price      = entry_price
                trade.binance_fill_qty         = fill_qty
                trade.binance_leverage         = leverage
                trade.binance_margin_type      = margin_type
                trade.binance_liq_price        = liq_price
                trade.binance_mark_price_entry = mark_price_entry
                trade.binance_wallet_at_open   = wallet_at_open
                trade.binance_synced           = True
                trade.binance_synced_at        = datetime.now(timezone.utc)
    except Exception as e:
        log.error("_update_trade_binance_fields: %s", e)


def _update_trade_binance_close(
    trade_id:         int,
    exit_price:       float,
    realized_pnl:     float,
    commission_total: float,
    funding_total:    float,
    net_pnl:          float,
    wallet_at_close:  float,
) -> None:
    try:
        with get_session() as db:
            trade = db.query(TradeModel).filter(TradeModel.id == trade_id).first()
            if trade:
                trade.binance_exit_price        = exit_price
                trade.binance_realized_pnl      = realized_pnl
                trade.binance_commission_total  = commission_total
                trade.binance_funding_total     = funding_total
                trade.binance_net_pnl           = net_pnl
                trade.binance_wallet_at_close   = wallet_at_close
                trade.binance_synced            = True
                trade.binance_synced_at         = datetime.now(timezone.utc)

                trade.net_pnl                  = net_pnl
                trade.realized_pnl_exchange    = realized_pnl
                trade.total_commission         = commission_total
                trade.funding_fees_paid        = abs(funding_total)
    except Exception as e:
        log.error("_update_trade_binance_close: %s", e)


def get_binance_record(trade_id: int) -> dict | None:
    try:
        with get_session() as db:
            record = db.query(BinanceTradeRecord).filter(
                BinanceTradeRecord.trade_id == trade_id
            ).first()
            if not record:
                return None
            return {
                "trade_id":               record.trade_id,
                "coin":                   record.coin,
                "direction":              record.direction,
                "entry_avg_price":        record.entry_avg_price,
                "entry_filled_qty":       record.entry_filled_qty,
                "entry_commission":       record.entry_commission,
                "entry_role":             record.entry_role,
                "exit_avg_price":         record.exit_avg_price,
                "exit_filled_qty":        record.exit_filled_qty,
                "exit_commission":        record.exit_commission,
                "exit_role":              record.exit_role,
                "leverage":               record.leverage,
                "margin_type":            record.margin_type,
                "position_margin":        record.position_margin,
                "liquidation_price":      record.liquidation_price,
                "mark_price_at_entry":    record.mark_price_at_entry,
                "mark_price_at_exit":     record.mark_price_at_exit,
                "wallet_balance_at_open": record.wallet_balance_at_open,
                "wallet_balance_at_close":record.wallet_balance_at_close,
                "total_commission":       record.total_commission,
                "total_funding":          record.total_funding,
                "gross_realized_pnl":     record.gross_realized_pnl,
                "net_pnl":                record.net_pnl,
                "income_fetched":         record.income_fetched,
                "synced_at":              record.synced_at.isoformat() if record.synced_at else None,
            }
    except Exception as e:
        log.error("get_binance_record: %s", e)
        return None


def get_account_summary() -> dict:
    try:
        with get_session() as db:
            latest = db.query(BinanceAccountSnapshot).order_by(
                BinanceAccountSnapshot.snapshot_at.desc()
            ).first()

            if not latest:
                return {}

            return {
                "wallet_balance":       latest.wallet_balance,
                "available_balance":    latest.available_balance,
                "total_unrealized_pnl": latest.total_unrealized_pnl,
                "total_margin_used":    latest.total_margin_used,
                "total_position_count": latest.total_position_count,
                "snapshot_at":          latest.snapshot_at.isoformat() if latest.snapshot_at else None,
            }
    except Exception as e:
        log.error("get_account_summary: %s", e)
        return {}


def get_funding_for_trade(trade_id: int) -> list:
    try:
        with get_session() as db:
            records = db.query(BinanceFundingRecord).filter(
                BinanceFundingRecord.trade_id == trade_id
            ).order_by(BinanceFundingRecord.funding_time.asc()).all()

            return [{
                "funding_time": r.funding_time.isoformat() if r.funding_time else None,
                "funding_rate": r.funding_rate,
                "funding_fee":  r.funding_fee,
                "mark_price":   r.mark_price_at_funding,
            } for r in records]
    except Exception as e:
        log.error("get_funding_for_trade: %s", e)
        return []


async def periodic_account_snapshot() -> None:
    try:
        await _snapshot_account(trigger="scheduled")
        log.debug("Periodic account snapshot saved")
    except Exception as e:
        log.error("periodic_account_snapshot: %s", e)


async def sync_unsynced_trades() -> int:
    try:
        from database import SessionLocal
        with SessionLocal() as db:
            unsynced = db.query(TradeModel).filter(
                TradeModel.outcome.in_(["win", "loss"]),
                TradeModel.binance_synced == False,
            ).all()

        count = 0
        for trade in unsynced:
            if not trade.coin:
                continue
            await _fetch_and_store_income(trade.id, trade.coin)
            count += 1
            await asyncio.sleep(0.5)

        if count:
            log.info("Synced %s unsynced trades with Binance income data", count)
        return count

    except Exception as e:
        log.error("sync_unsynced_trades: %s", e)
        return 0