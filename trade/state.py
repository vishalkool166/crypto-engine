from datetime import datetime, timezone
from database import Trade, DailyRisk, get_session
from config import cfg
import logging

log = logging.getLogger(__name__)


class TradeState:
    IDLE     = "idle"
    ENTRY    = "entry"
    IN_TRADE = "in_trade"
    EXIT     = "exit"


class StateManager:

    def __init__(self):
        self._active_trade: Trade | None = None
        self._health_state: str          = "HEALTHY"
        self._health_data:  dict         = {}
        self._paused:       bool         = False
        self._load_active_trade()

    def _load_active_trade(self):
        try:
            with get_session() as db:
                trade = db.query(Trade).filter(Trade.is_active == True).first()
                if trade:
                    self._active_trade = trade
                    log.info(
                        f"Resumed active trade: {trade.coin} {trade.direction} "
                        f"State: {trade.state} TP1 hit: {self._check_tp1_hit(trade)}"
                    )
                else:
                    self._active_trade = None
                    log.info("No active trade found — idle")
        except Exception as e:
            log.warning(f"Could not load active trade: {e}")
            self._active_trade = None

    def _check_tp1_hit(self, trade: Trade) -> bool:
        if not trade or not trade.sl_price or not trade.entry_price:
            return False
        return abs(trade.sl_price - trade.entry_price) / trade.entry_price < 0.002

    @property
    def is_idle(self) -> bool:
        return self._active_trade is None

    @property
    def is_in_trade(self) -> bool:
        return (
            self._active_trade is not None and
            self._active_trade.state == TradeState.IN_TRADE
        )

    @property
    def current_trade(self) -> Trade | None:
        return self._active_trade

    @property
    def current_state(self) -> str:
        if self._active_trade is None:
            return TradeState.IDLE
        return self._active_trade.state

    @property
    def is_tp1_hit(self) -> bool:
        return self._check_tp1_hit(self._active_trade)

    @property
    def health_state(self) -> str:
        return self._health_state

    @property
    def health_data(self) -> dict:
        return self._health_data

    @property
    def is_paused(self) -> bool:
        return self._paused

    def pause(self):
        self._paused = True
        log.info("Bot paused — auto-execution disabled")

    def resume(self):
        self._paused = False
        log.info("Bot resumed — auto-execution enabled")

    def update_health(self, health: dict):
        self._health_state = health.get("state", "HEALTHY")
        self._health_data  = health
        log.info(
            f"Health updated: {self._health_state} "
            f"warnings:{len(health.get('warnings', []))} "
            f"failures:{len(health.get('failures', []))}"
        )

    def reset_health(self):
        self._health_state = "HEALTHY"
        self._health_data  = {}

    def refresh(self):
        if self._active_trade is None:
            return
        try:
            with get_session() as db:
                trade = db.query(Trade).filter(Trade.id == self._active_trade.id).first()
                if not trade or not trade.is_active:
                    self._active_trade = None
                    self.reset_health()
                    log.info("Refresh: trade no longer active — idle")
                else:
                    self._active_trade = trade
                    log.debug(
                        f"Refresh: {trade.coin} sl:{trade.sl_price} "
                        f"tp1_hit:{self._check_tp1_hit(trade)}"
                    )
        except Exception as e:
            log.error(f"Refresh error: {e}")

    def set_entry(self, trade: Trade):
        self._active_trade = trade
        self.reset_health()
        self._update_state(trade, TradeState.ENTRY)
        log.info(f"State → ENTRY: {trade.coin} {trade.direction}")

    def set_in_trade(self, trade: Trade):
        self._active_trade = trade
        self._update_state(trade, TradeState.IN_TRADE)
        log.info(f"State → IN_TRADE: {trade.coin} {trade.direction}")

    def set_exit(self, trade: Trade):
        self._update_state(trade, TradeState.EXIT)
        log.info(f"State → EXIT: {trade.coin} {trade.direction}")

    def set_idle(self):
        self._active_trade = None
        self.reset_health()
        log.info("State → IDLE")

    def can_trade_today(self) -> dict:
        today = str(datetime.now(timezone.utc).date())
        try:
            with get_session() as db:
                risk = db.query(DailyRisk).filter(DailyRisk.date == today).first()

                if not risk:
                    return {
                        "allowed":      True,
                        "trades_taken": 0,
                        "total_loss":   0.0,
                        "reason":       None
                    }

                if risk.cap_hit:
                    return {
                        "allowed":      False,
                        "trades_taken": risk.trades_taken,
                        "total_loss":   risk.total_loss,
                        "reason":       f"Daily loss cap hit — ${abs(risk.total_loss):.4f} lost today"
                    }

                if risk.trades_taken >= cfg.MAX_TRADES_PER_DAY:
                    return {
                        "allowed":      False,
                        "trades_taken": risk.trades_taken,
                        "total_loss":   risk.total_loss,
                        "reason":       f"Max {cfg.MAX_TRADES_PER_DAY} trades reached today"
                    }

                daily_cap = cfg.CAPITAL * cfg.DAILY_LOSS_CAP_PCT
                if abs(risk.total_loss) >= daily_cap:
                    risk.cap_hit = True
                    return {
                        "allowed":      False,
                        "trades_taken": risk.trades_taken,
                        "total_loss":   risk.total_loss,
                        "reason":       f"Daily loss cap ${daily_cap:.4f} reached"
                    }

                return {
                    "allowed":      True,
                    "trades_taken": risk.trades_taken,
                    "total_loss":   risk.total_loss,
                    "reason":       None
                }
        except Exception as e:
            log.error(f"can_trade_today error: {e}")
            return {"allowed": True, "trades_taken": 0, "total_loss": 0.0, "reason": None}

    def record_trade_open(self):
        today = str(datetime.now(timezone.utc).date())
        try:
            with get_session() as db:
                risk = db.query(DailyRisk).filter(DailyRisk.date == today).first()
                if not risk:
                    risk = DailyRisk(
                        date=today, trades_taken=1,
                        total_pnl=0.0, total_loss=0.0, cap_hit=False
                    )
                    db.add(risk)
                else:
                    risk.trades_taken += 1
                log.info(f"Trade open recorded — trades today: {risk.trades_taken}")
        except Exception as e:
            log.error(f"record_trade_open error: {e}")

    def undo_trade_open(self):
        today = str(datetime.now(timezone.utc).date())
        try:
            with get_session() as db:
                risk = db.query(DailyRisk).filter(DailyRisk.date == today).first()
                if risk and risk.trades_taken > 0:
                    risk.trades_taken -= 1
                    log.info(f"Trade open undone — trades today: {risk.trades_taken}")
        except Exception as e:
            log.error(f"undo_trade_open error: {e}")

    def record_partial_pnl(self, pnl: float):
        today = str(datetime.now(timezone.utc).date())
        try:
            with get_session() as db:
                risk = db.query(DailyRisk).filter(DailyRisk.date == today).first()
                if not risk:
                    risk = DailyRisk(
                        date=today, trades_taken=0,
                        total_pnl=0.0, total_loss=0.0, cap_hit=False
                    )
                    db.add(risk)
                risk.total_pnl += pnl
                if pnl < 0:
                    risk.total_loss += pnl
                    daily_cap = cfg.CAPITAL * cfg.DAILY_LOSS_CAP_PCT
                    if abs(risk.total_loss) >= daily_cap:
                        risk.cap_hit = True
                        log.warning(f"Daily cap hit on partial: ${risk.total_loss:.4f}")
                log.info(f"Partial PnL recorded: ${pnl:.4f} — total today: ${risk.total_pnl:.4f}")
        except Exception as e:
            log.error(f"record_partial_pnl error: {e}")

    def record_trade_close(self, pnl: float):
        today = str(datetime.now(timezone.utc).date())
        try:
            with get_session() as db:
                risk = db.query(DailyRisk).filter(DailyRisk.date == today).first()
                if not risk:
                    risk = DailyRisk(
                        date=today, trades_taken=0,
                        total_pnl=0.0, total_loss=0.0, cap_hit=False
                    )
                    db.add(risk)
                risk.total_pnl += pnl
                if pnl < 0:
                    risk.total_loss += pnl
                    daily_cap = cfg.CAPITAL * cfg.DAILY_LOSS_CAP_PCT
                    if abs(risk.total_loss) >= daily_cap:
                        risk.cap_hit = True
                        log.warning(f"Daily loss cap hit: ${abs(risk.total_loss):.4f}")
                log.info(f"Trade close PnL recorded: ${pnl:.4f} — total today: ${risk.total_pnl:.4f}")
        except Exception as e:
            log.error(f"record_trade_close error: {e}")

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