from datetime import datetime, date
from sqlalchemy.orm import Session
from database import Trade, DailyRisk, SessionLocal
from config import cfg
import logging

log = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════
# TRADE STATES
# ═══════════════════════════════════════════════════════
class TradeState:
    IDLE     = "idle"
    ENTRY    = "entry"
    IN_TRADE = "in_trade"
    EXIT     = "exit"


# ═══════════════════════════════════════════════════════
# STATE MANAGER
# ═══════════════════════════════════════════════════════
class StateManager:

    def __init__(self):
        self._active_trade: Trade | None = None
        self._load_active_trade()

    # ═══════════════════════════════════════════════════
    # LOAD ON STARTUP
    # resumes any trade that was active before restart
    # ═══════════════════════════════════════════════════
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
            log.warning(
                f"Could not load active trade "
                f"(first run?): {e}"
            )
            self._active_trade = None

    # ═══════════════════════════════════════════════════
    # TP1 HIT CHECK
    # SL moved to entry = TP1 was hit
    # stored in DB — survives restarts
    # ═══════════════════════════════════════════════════
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
        """
        Public property — used by routes.py
        and manager.py to check phase.
        """
        return self._check_tp1_hit(self._active_trade)

    # ═══════════════════════════════════════════════════
    # REFRESH ACTIVE TRADE FROM DB
    # call this before any read that needs fresh data
    # ═══════════════════════════════════════════════════
    def refresh(self):
        """
        Re-reads active trade from DB.
        Ensures sl_price, tp1_order_id etc
        are always current after monitor updates.
        """
        if self._active_trade is None:
            return

        db = SessionLocal()
        try:
            trade = db.query(Trade).filter(
                Trade.id == self._active_trade.id
            ).first()

            if not trade or not trade.is_active:
                self._active_trade = None
                log.info(
                    "Refresh: trade no longer active — idle"
                )
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
        self._update_state(trade, TradeState.ENTRY)
        log.info(
            f"State → ENTRY: "
            f"{trade.coin} {trade.direction}"
        )

    def set_in_trade(self, trade: Trade):
        self._active_trade = trade
        self._update_state(trade, TradeState.IN_TRADE)
        log.info(
            f"State → IN_TRADE: "
            f"{trade.coin} {trade.direction}"
        )

    def set_exit(self, trade: Trade):
        self._update_state(trade, TradeState.EXIT)
        log.info(
            f"State → EXIT: "
            f"{trade.coin} {trade.direction}"
        )

    def set_idle(self):
        self._active_trade = None
        log.info("State → IDLE")

    # ═══════════════════════════════════════════════════
    # DAILY RISK CHECKS
    # ═══════════════════════════════════════════════════
    def can_trade_today(self) -> dict:
        db    = SessionLocal()
        today = str(date.today())
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

            # Cap already flagged
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

            # Max trades
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

            # Loss cap check
            daily_cap = cfg.CAPITAL * cfg.DAILY_LOSS_CAP_PCT
            if abs(risk.total_loss) >= daily_cap:
                risk.cap_hit = True
                db.commit()
                return {
                    "allowed":      False,
                    "trades_taken": risk.trades_taken,
                    "total_loss":   risk.total_loss,
                    "reason": (
                        f"Daily loss cap "
                        f"${daily_cap:.4f} reached"
                    )
                }

            return {
                "allowed":      True,
                "trades_taken": risk.trades_taken,
                "total_loss":   risk.total_loss,
                "reason":       None
            }

        finally:
            db.close()

    # ═══════════════════════════════════════════════════
    # RECORD TRADE OPEN
    # increments trades_taken counter
    # ═══════════════════════════════════════════════════
    def record_trade_open(self):
        db    = SessionLocal()
        today = str(date.today())
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

    # ═══════════════════════════════════════════════════
    # RECORD PARTIAL PNL
    # called immediately when TP1 hits
    # so dashboard shows real numbers without
    # waiting for full trade close
    # ═══════════════════════════════════════════════════
    def record_partial_pnl(self, pnl: float):
        """
        Records TP1 partial PnL to DailyRisk.
        Called from manager._handle_tp1_hit().
        Ensures today_pnl updates immediately.
        """
        db    = SessionLocal()
        today = str(date.today())
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

            # TP1 should always be positive
            # but guard for edge cases
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
                f"Partial PnL recorded: "
                f"${pnl:.4f} (TP1 hit) — "
                f"total today: ${risk.total_pnl:.4f}"
            )

        except Exception as e:
            log.error(f"record_partial_pnl error: {e}")
            db.rollback()
        finally:
            db.close()

    # ═══════════════════════════════════════════════════
    # RECORD TRADE CLOSE
    # called when trade fully closes (TP2, SL, manual)
    # adds remaining PnL to daily totals
    # ═══════════════════════════════════════════════════
    def record_trade_close(self, pnl: float):
        """
        Records final close PnL.
        If TP1 was hit — this is only the 30% remainder.
        TP1 partial was already recorded via
        record_partial_pnl().
        """
        db    = SessionLocal()
        today = str(date.today())
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
                f"Trade close PnL recorded: "
                f"${pnl:.4f} — "
                f"total today: ${risk.total_pnl:.4f}"
            )

        except Exception as e:
            log.error(f"record_trade_close error: {e}")
            db.rollback()
        finally:
            db.close()

    # ═══════════════════════════════════════════════════
    # GET DAILY SUMMARY
    # convenience method — used by telegram /daily
    # ═══════════════════════════════════════════════════
    def get_daily_summary(self) -> dict:
        db    = SessionLocal()
        today = str(date.today())
        try:
            risk = db.query(DailyRisk).filter(
                DailyRisk.date == today
            ).first()

            daily_cap = cfg.CAPITAL * cfg.DAILY_LOSS_CAP_PCT

            if not risk:
                return {
                    "date":             today,
                    "trades_taken":     0,
                    "total_pnl":        0.0,
                    "total_loss":       0.0,
                    "cap_hit":          False,
                    "remaining_trades": cfg.MAX_TRADES_PER_DAY,
                    "remaining_loss":   daily_cap
                }

            return {
                "date":         today,
                "trades_taken": risk.trades_taken,
                "total_pnl":    round(risk.total_pnl, 4),
                "total_loss":   round(risk.total_loss, 4),
                "cap_hit":      risk.cap_hit,
                "remaining_trades": max(
                    0,
                    cfg.MAX_TRADES_PER_DAY -
                    risk.trades_taken
                ),
                "remaining_loss": round(
                    max(
                        0,
                        daily_cap - abs(risk.total_loss)
                    ), 4
                )
            }

        finally:
            db.close()

    # ═══════════════════════════════════════════════════
    # INTERNAL — UPDATE STATE IN DB
    # ═══════════════════════════════════════════════════
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


# ── GLOBAL INSTANCE ──
state_manager = StateManager()