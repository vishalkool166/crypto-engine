from datetime import datetime, timezone
from database import Trade, DailyRisk, get_session
from config import cfg
import logging
import asyncio

log = logging.getLogger(__name__)


class TradeState:
    IDLE     = "idle"
    ENTRY    = "entry"
    IN_TRADE = "in_trade"
    EXIT     = "exit"


class StateManager:

    def __init__(self):
        self._active_trades: dict[int, Trade] = {}
        self._health_states: dict[int, str]   = {}
        self._health_data:   dict[int, dict]  = {}
        self._paused:        bool             = False
        self._trade_locks:   dict[int, asyncio.Lock] = {}
        self._load_active_trades()

    def _load_active_trades(self):
        try:
            with get_session() as db:
                trades = db.query(Trade).filter(Trade.is_active == True).all()
                for trade in trades:
                    self._active_trades[trade.id] = trade
                    self._health_states[trade.id] = "HEALTHY"
                    self._health_data[trade.id]   = {}
                    self._trade_locks[trade.id]   = asyncio.Lock()
                if trades:
                    log.info(f"Resumed {len(trades)} active trade(s)")
                else:
                    log.info("No active trades — idle")
        except Exception as e:
            log.warning(f"Could not load active trades: {e}")

    def get_trade_lock(self, trade_id: int) -> asyncio.Lock:
        if trade_id not in self._trade_locks:
            self._trade_locks[trade_id] = asyncio.Lock()
        return self._trade_locks[trade_id]

    def _check_tp1_hit(self, trade: Trade) -> bool:
        if not trade:
            return False
        if trade.tp1_hit:
            return True
        try:
            with get_session() as db:
                t = db.query(Trade).filter(Trade.id == trade.id).first()
                if t and t.tp1_hit:
                    trade.tp1_hit = True
                    return True
        except Exception:
            pass
        return False

    @property
    def is_idle(self) -> bool:
        return len(self._active_trades) == 0

    @property
    def is_in_trade(self) -> bool:
        return len(self._active_trades) > 0

    @property
    def active_trades(self) -> dict[int, Trade]:
        return self._active_trades

    @property
    def current_trade(self) -> Trade | None:
        if not self._active_trades:
            return None
        return next(iter(self._active_trades.values()))

    @property
    def current_state(self) -> str:
        if not self._active_trades:
            return TradeState.IDLE
        return self.current_trade.state

    @property
    def is_tp1_hit(self) -> bool:
        trade = self.current_trade
        return self._check_tp1_hit(trade)

    def is_tp1_hit_for(self, trade_id: int) -> bool:
        trade = self._active_trades.get(trade_id)
        return self._check_tp1_hit(trade)

    @property
    def health_state(self) -> str:
        trade = self.current_trade
        if not trade:
            return "HEALTHY"
        return self._health_states.get(trade.id, "HEALTHY")

    def health_state_for(self, trade_id: int) -> str:
        return self._health_states.get(trade_id, "HEALTHY")

    @property
    def health_data(self) -> dict:
        trade = self.current_trade
        if not trade:
            return {}
        return self._health_data.get(trade.id, {})

    def health_data_for(self, trade_id: int) -> dict:
        return self._health_data.get(trade_id, {})

    @property
    def is_paused(self) -> bool:
        return self._paused

    def pause(self):
        self._paused = True
        log.info("Bot paused")

    def resume(self):
        self._paused = False
        log.info("Bot resumed")

    def update_health(self, health: dict, trade_id: int = None):
        if trade_id is None:
            trade = self.current_trade
            if trade:
                trade_id = trade.id
        if trade_id:
            self._health_states[trade_id] = health.get("state", "HEALTHY")
            self._health_data[trade_id]   = health

    def reset_health(self, trade_id: int = None):
        if trade_id is None:
            trade = self.current_trade
            if trade:
                trade_id = trade.id
        if trade_id:
            self._health_states[trade_id] = "HEALTHY"
            self._health_data[trade_id]   = {}

    def can_open_trade(self) -> bool:
        from trade.risk import get_current_tier
        tier = get_current_tier()
        return len(self._active_trades) < tier["max_trades"]

    def refresh(self):
        to_remove = []
        for tid, trade in list(self._active_trades.items()):
            try:
                with get_session() as db:
                    t = db.query(Trade).filter(Trade.id == tid).first()
                    if not t or not t.is_active:
                        to_remove.append(tid)
                    else:
                        self._active_trades[tid] = t
            except Exception as e:
                log.error(f"Refresh error trade {tid}: {e}")
        for tid in to_remove:
            self._remove_trade(tid)

    def _remove_trade(self, trade_id: int):
        self._active_trades.pop(trade_id, None)
        self._health_states.pop(trade_id, None)
        self._health_data.pop(trade_id, None)
        self._trade_locks.pop(trade_id, None)

    def set_entry(self, trade: Trade):
        self._active_trades[trade.id] = trade
        self._health_states[trade.id] = "HEALTHY"
        self._health_data[trade.id]   = {}
        self._trade_locks[trade.id]   = asyncio.Lock()
        self._update_state(trade, TradeState.ENTRY)
        log.info(f"State → ENTRY: {trade.coin} {trade.direction}")

    def set_in_trade(self, trade: Trade):
        self._active_trades[trade.id] = trade
        if trade.id not in self._trade_locks:
            self._trade_locks[trade.id] = asyncio.Lock()
        self._update_state(trade, TradeState.IN_TRADE)
        log.info(f"State → IN_TRADE: {trade.coin} {trade.direction}")

    def set_idle(self, trade_id: int = None):
        if trade_id:
            self._remove_trade(trade_id)
            log.info(f"Trade {trade_id} removed — active: {len(self._active_trades)}")
        else:
            self._active_trades.clear()
            self._health_states.clear()
            self._health_data.clear()
            self._trade_locks.clear()
            log.info("State → IDLE (all trades cleared)")

    def undo_trade_open(self, trade_id: int):
        self._remove_trade(trade_id)
        self._undo_daily_open()

    def _undo_daily_open(self):
        today = str(datetime.now(timezone.utc).date())
        try:
            with get_session() as db:
                risk = db.query(DailyRisk).filter(DailyRisk.date == today).first()
                if risk and risk.trades_taken > 0:
                    risk.trades_taken -= 1
        except Exception as e:
            log.error(f"undo_trade_open error: {e}")

    def can_trade_today(self) -> dict:
        today = str(datetime.now(timezone.utc).date())
        from trade.risk import get_current_tier
        tier = get_current_tier()
        try:
            with get_session() as db:
                risk = db.query(DailyRisk).filter(DailyRisk.date == today).first()

                if not risk:
                    return {"allowed": True, "trades_taken": 0, "total_loss": 0.0, "reason": None}

                capital   = tier["balance"] or cfg.CAPITAL
                daily_cap = capital * cfg.DAILY_LOSS_CAP_PCT

                if risk.cap_hit:
                    return {"allowed": False, "trades_taken": risk.trades_taken,
                            "total_loss": risk.total_loss,
                            "reason": f"Daily loss cap hit — ${abs(risk.total_loss):.4f} lost today"}

                if risk.trades_taken >= tier["max_trades"]:
                    return {"allowed": False, "trades_taken": risk.trades_taken,
                            "total_loss": risk.total_loss,
                            "reason": f"Max {tier['max_trades']} trades reached today"}

                if abs(risk.total_loss) >= daily_cap:
                    risk.cap_hit = True
                    return {"allowed": False, "trades_taken": risk.trades_taken,
                            "total_loss": risk.total_loss,
                            "reason": f"Daily loss cap ${daily_cap:.4f} reached"}

                return {"allowed": True, "trades_taken": risk.trades_taken,
                        "total_loss": risk.total_loss, "reason": None}
        except Exception as e:
            log.error(f"can_trade_today error: {e}")
            return {"allowed": True, "trades_taken": 0, "total_loss": 0.0, "reason": None}

    def record_trade_open(self):
        today = str(datetime.now(timezone.utc).date())
        from trade.risk import get_current_tier
        tier = get_current_tier()
        try:
            with get_session() as db:
                risk = db.query(DailyRisk).filter(DailyRisk.date == today).first()
                if not risk:
                    risk = DailyRisk(date=today, trades_taken=1,
                                     total_pnl=0.0, total_loss=0.0,
                                     cap_hit=False, tier=tier["tier"])
                    db.add(risk)
                else:
                    risk.trades_taken += 1
        except Exception as e:
            log.error(f"record_trade_open error: {e}")

    def record_partial_pnl(self, pnl: float):
        today = str(datetime.now(timezone.utc).date())
        from trade.risk import get_current_tier
        tier = get_current_tier()
        try:
            with get_session() as db:
                risk = db.query(DailyRisk).filter(DailyRisk.date == today).first()
                if not risk:
                    risk = DailyRisk(date=today, trades_taken=0,
                                     total_pnl=0.0, total_loss=0.0,
                                     cap_hit=False, tier=tier["tier"])
                    db.add(risk)
                risk.total_pnl += pnl
                if pnl < 0:
                    risk.total_loss += pnl
                    capital   = tier["balance"] or cfg.CAPITAL
                    daily_cap = capital * cfg.DAILY_LOSS_CAP_PCT
                    if abs(risk.total_loss) >= daily_cap:
                        risk.cap_hit = True
        except Exception as e:
            log.error(f"record_partial_pnl error: {e}")

    def record_trade_close(self, pnl: float):
        import trade.risk as risk_module
        risk_module._cap_warning_sent = False
        today = str(datetime.now(timezone.utc).date())
        from trade.risk import get_current_tier, get_tier_config
        tier = get_current_tier()
        try:
            with get_session() as db:
                risk = db.query(DailyRisk).filter(DailyRisk.date == today).first()
                if not risk:
                    risk = DailyRisk(date=today, trades_taken=0,
                                    total_pnl=0.0, total_loss=0.0,
                                    cap_hit=False, tier=tier["tier"])
                    db.add(risk)
                risk.total_pnl += pnl
                if pnl < 0:
                    risk.total_loss += pnl
                    capital   = tier["balance"] or cfg.CAPITAL
                    daily_cap = capital * cfg.DAILY_LOSS_CAP_PCT
                    if abs(risk.total_loss) >= daily_cap:
                        risk.cap_hit = True
                        log.warning(f"Daily loss cap hit: ${abs(risk.total_loss):.4f}")
        except Exception as e:
            log.error(f"record_trade_close error: {e}")

        if cfg.PAPER_TRADING:
            import runtime_state as rs
            current = rs.get_balance_cache().get("balance", cfg.CAPITAL)
            new_balance = current + pnl
            if new_balance > 0:
                rs.set_paper_balance(new_balance)
                rs.set_balance_cache(new_balance)
                new_tier = get_tier_config(new_balance)
                rs.set_tier_config(new_tier)
                cfg.CAPITAL = new_balance

    def _update_state(self, trade: Trade, state: str):
        try:
            with get_session() as db:
                t = db.query(Trade).filter(Trade.id == trade.id).first()
                if t:
                    t.state     = state
                    trade.state = state
        except Exception as e:
            log.error(f"_update_state error: {e}")


state_manager = StateManager()