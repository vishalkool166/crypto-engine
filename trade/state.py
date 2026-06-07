from datetime import datetime, timezone, date
from database import Trade, DailyRisk, SessionLocal
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
            db = SessionLocal()
            try:
                trade = db.query(Trade).filter(
                    Trade.is_active == True
                ).first()

                if trade:
                    self._active_trade = trade
                    log.info(
                        f"Resumed active trade: "
                        f"{trade.coin} {trade.direction} "
                        f"State: {trade.state} "
                        f"TP1 hit: {self._check_tp1_hit(trade)}"
                    )
                else:
                    self._active_trade = None
                    log.info("No active trade found — idle")
            finally:
                db.close()
        except Exception as e:
            log.warning(f"Could not load active trade: {e}")
            self._active_trade = None

    def _check_tp1_hit(self, trade: Trade) -> bool:
        if not trade:
            return False
        if not trade.sl_price or not trade.entry_price:
            return False
        return (
            abs(trade.sl_price - trade.entry_price) /
            trade.entry_price < 0.001
        )

    # ═══════════════════════════════════════════════════
    # GETTERS
    # ═══════════════════════════════════════════════════
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

    # ═══════════════════════════════════════════════════
    # PAUSE / RESUME
    # ═══════════════════════════════════════════════════
    def pause(self):
        self._paused = True
        log.info("Bot paused — auto-execution disabled")

    def resume(self):
        self._paused = False
        log.info("Bot resumed — auto-execution enabled")

    # ═══════════════════════════════════════════════════
    # HEALTH
    # ═══════════════════════════════════════════════════
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

    # ═══════════════════════════════════════════════════
    # REFRESH
    # ═══════════════════════════════════════════════════
    def refresh(self):
        if self._active_trade is None:
            return

        db = SessionLocal()
        try:
            trade = db.query(Trade).filter(
                Trade.id == self._active_trade.id
            ).first()

            if not trade or not trade.is_active:
                self._active_trade = None
                self.reset_health()
                log.info("Refresh: trade no longer active — idle")
            else:
                self._active_trade = trade
                log.debug(
                    f"Refresh: {trade.coin} "
                    f"sl:{trade.sl_price} "
                    f"tp1_hit:{self._check_tp1_hit(trade)}"
                )
        except Exception as e:
            log.error(f"Refresh error: {e}")
        finally:
            db.close()

    # ═══════════════════════════════════════════════════
    # STATE TRANSITIONS
    # ═══════════════════════════════════════════════════
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

    # ═══════════════════════════════════════════════════
    # DAILY RISK
    # ═══════════════════════════════════════════════════
    def can_trade_today(self) -> dict:
        db    = SessionLocal()
        today = str(datetime.now(timezone.utc).date())
        try:
            risk = db.query(DailyRisk).filter(
                DailyRisk.date == today
            ).first()

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
                    "reason": (
                        f"Daily loss cap hit — "
                        f"${abs(risk.total_loss):.4f} lost today"
                    )
                }

            if risk.trades_taken >= cfg.MAX_TRADES_PER_DAY:
                return {
                    "allowed":      False,
                    "trades_taken": risk.trades_taken,
                    "total_loss":   risk.total_loss,
                    "reason": (
                        f"Max {cfg.MAX_TRADES_PER_DAY} "
                        f"trades reached today"
                    )
                }

            daily_cap = cfg.CAPITAL * cfg.DAILY_LOSS_CAP_PCT
            if abs(risk.total_loss) >= daily_cap:
                risk.cap_hit = True
                db.commit()
                return {
                    "allowed":      False,
                    "trades_taken": risk.trades_taken,
                    "total_loss":   risk.total_loss,
                    "reason": f"Daily loss cap ${daily_cap:.4f} reached"
                }

            return {
                "allowed":      True,
                "trades_taken": risk.trades_taken,
                "total_loss":   risk.total_loss,
                "reason":       None
            }

        finally:
            db.close()

    def record_trade_open(self):
        db    = SessionLocal()
        today = str(datetime.now(timezone.utc).date())
        try:
            risk = db.query(DailyRisk).filter(
                DailyRisk.date == today
            ).first()

            if not risk:
                risk = DailyRisk(
                    date         = today,
                    trades_taken = 1,
                    total_pnl    = 0.0,
                    total_loss   = 0.0,
                    cap_hit      = False
                )
                db.add(risk)
            else:
                risk.trades_taken += 1

            db.commit()
            log.info(
                f"Trade open recorded — "
                f"trades today: {risk.trades_taken}"
            )

        except Exception as e:
            log.error(f"record_trade_open error: {e}")
            db.rollback()
        finally:
            db.close()

    def record_partial_pnl(self, pnl: float):
        db    = SessionLocal()
        today = str(datetime.now(timezone.utc).date())
        try:
            risk = db.query(DailyRisk).filter(
                DailyRisk.date == today
            ).first()

            if not risk:
                risk = DailyRisk(
                    date         = today,
                    trades_taken = 0,
                    total_pnl    = 0.0,
                    total_loss   = 0.0,
                    cap_hit      = False
                )
                db.add(risk)

            risk.total_pnl += pnl

            if pnl < 0:
                risk.total_loss += pnl
                daily_cap = cfg.CAPITAL * cfg.DAILY_LOSS_CAP_PCT
                if abs(risk.total_loss) >= daily_cap:
                    risk.cap_hit = True
                    log.warning(
                        f"Daily cap hit on partial: "
                        f"${risk.total_loss:.4f}"
                    )

            db.commit()
            log.info(
                f"Partial PnL recorded: ${pnl:.4f} — "
                f"total today: ${risk.total_pnl:.4f}"
            )

        except Exception as e:
            log.error(f"record_partial_pnl error: {e}")
            db.rollback()
        finally:
            db.close()

    def record_trade_close(self, pnl: float):
        db    = SessionLocal()
        today = str(datetime.now(timezone.utc).date())
        try:
            risk = db.query(DailyRisk).filter(
                DailyRisk.date == today
            ).first()

            if not risk:
                risk = DailyRisk(
                    date         = today,
                    trades_taken = 0,
                    total_pnl    = 0.0,
                    total_loss   = 0.0,
                    cap_hit      = False
                )
                db.add(risk)

            risk.total_pnl += pnl

            if pnl < 0:
                risk.total_loss += pnl
                daily_cap = cfg.CAPITAL * cfg.DAILY_LOSS_CAP_PCT
                if abs(risk.total_loss) >= daily_cap:
                    risk.cap_hit = True
                    log.warning(
                        f"Daily loss cap hit: "
                        f"${abs(risk.total_loss):.4f}"
                    )

            db.commit()
            log.info(
                f"Trade close PnL recorded: ${pnl:.4f} — "
                f"total today: ${risk.total_pnl:.4f}"
            )

        except Exception as e:
            log.error(f"record_trade_close error: {e}")
            db.rollback()
        finally:
            db.close()

    def _update_state(self, trade: Trade, state: str):
        db = SessionLocal()
        try:
            t = db.query(Trade).filter(
                Trade.id == trade.id
            ).first()
            if t:
                t.state     = state
                db.commit()
                trade.state = state
        except Exception as e:
            log.error(f"_update_state error: {e}")
            db.rollback()
        finally:
            db.close()


state_manager = StateManager()