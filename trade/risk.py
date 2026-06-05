from config import cfg
from database import SessionLocal, Trade, DailyRisk
from datetime import date
import logging

log = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════
# RISK GUARD
# called before every trade attempt
# ═══════════════════════════════════════════════════════
class RiskGuard:

    # ── POSITION SIZING ──
    def calculate_position(
        self,
        entry:    float,
        sl:       float,
        capital:  float = cfg.CAPITAL,
        leverage: int   = cfg.LEVERAGE
    ) -> dict:
        """
        Calculates position size based on
        fixed risk % per trade.
        """
        sl_dist  = abs(entry - sl)
        sl_pct   = sl_dist / entry

        if sl_pct == 0:
            return {"valid": False, "reason": "SL equals entry"}

        # Dollar risk
        risk_amt = capital * cfg.RISK_PCT_PER_TRADE

        # Position size
        pos_size = risk_amt / sl_pct
        margin   = pos_size / leverage

        # Sanity checks
        if margin > capital:
            return {
                "valid":  False,
                "reason": f"Margin ${margin:.2f} exceeds capital ${capital:.2f}"
            }

        if risk_amt < 0.10:
            return {
                "valid":  False,
                "reason": f"Risk amount ${risk_amt:.2f} too small — fees will eat it"
            }

        # Fee estimate — Binance futures taker 0.06%
        fee_entry = pos_size * 0.0006
        fee_exit  = pos_size * 0.0006
        total_fee = fee_entry + fee_exit

        # Net risk after fees
        net_risk = risk_amt - total_fee

        if net_risk <= 0:
            return {
                "valid":  False,
                "reason": f"Fees ${total_fee:.4f} exceed risk ${risk_amt:.2f}"
            }

        return {
            "valid":      True,
            "risk_amt":   round(risk_amt, 4),
            "pos_size":   round(pos_size, 4),
            "margin":     round(margin, 4),
            "sl_pct":     round(sl_pct * 100, 4),
            "fee_est":    round(total_fee, 4),
            "net_risk":   round(net_risk, 4),
            "leverage":   leverage
        }

    # ── PRE TRADE CHECKS ──
    def pre_trade_check(
        self,
        signal: dict,
        capital: float = cfg.CAPITAL
    ) -> dict:
        """
        Full check before placing any trade.
        Returns allowed True/False with reason.
        """
        reasons = []

        # 1. Grade filter
        if signal.get("grade") not in cfg.MIN_GRADE_TO_TRADE:
            reasons.append(
                f"Grade {signal.get('grade')} below minimum — "
                f"need {cfg.MIN_GRADE_TO_TRADE}"
            )

        # 2. Direction must be LONG or SHORT
        if signal.get("direction") not in ["LONG", "SHORT"]:
            reasons.append(
                f"Invalid direction: {signal.get('direction')}"
            )

        # 3. Minimum signal conditions — audit requirement
        if cfg.REQUIRE_SWEEP_OR_DISPLACEMENT:
            sweep_ok = signal.get("sweep_score", 0) >= 6
            disp_ok  = signal.get("disp_score", 0) >= 6
            if not sweep_ok and not disp_ok:
                reasons.append(
                    "Neither sweep nor displacement confirmed — "
                    "minimum condition not met"
                )

        # 4. Funding rate check
        funding = signal.get("funding", 0) * 100
        if abs(funding) > 0.08:
            reasons.append(
                f"Extreme funding {funding:.4f}% — squeeze risk"
            )

        # 5. Position sizing check
        sizing = self.calculate_position(
            entry=signal.get("entry", 0),
            sl=signal.get("sl", 0),
            capital=capital
        )
        if not sizing["valid"]:
            reasons.append(f"Sizing failed: {sizing['reason']}")

        if reasons:
            return {
                "allowed": False,
                "reasons": reasons,
                "sizing":  None
            }

        return {
            "allowed": True,
            "reasons": [],
            "sizing":  sizing
        }

    # ── DAILY STATS ──
    def get_daily_stats(self) -> dict:
        db    = SessionLocal()
        today = str(date.today())
        try:
            risk = db.query(DailyRisk).filter(
                DailyRisk.date == today
            ).first()

            if not risk:
                return {
                    "date":         today,
                    "trades_taken": 0,
                    "total_pnl":    0.0,
                    "total_loss":   0.0,
                    "cap_hit":      False,
                    "remaining_trades": cfg.MAX_TRADES_PER_DAY,
                    "remaining_loss":   cfg.CAPITAL * cfg.DAILY_LOSS_CAP_PCT
                }

            daily_cap = cfg.CAPITAL * cfg.DAILY_LOSS_CAP_PCT
            return {
                "date":             today,
                "trades_taken":     risk.trades_taken,
                "total_pnl":        round(risk.total_pnl, 4),
                "total_loss":       round(risk.total_loss, 4),
                "cap_hit":          risk.cap_hit,
                "remaining_trades": max(0, cfg.MAX_TRADES_PER_DAY - risk.trades_taken),
                "remaining_loss":   round(max(0, daily_cap - abs(risk.total_loss)), 4)
            }
        finally:
            db.close()

    # ── UNREALIZED PNL ──
    def calculate_unrealized_pnl(
        self,
        direction:     str,
        entry_price:   float,
        current_price: float,
        pos_size:      float
    ) -> float:
        """
        Calculates unrealized PnL for open trade.
        """
        if direction == "LONG":
            pnl = (current_price - entry_price) / entry_price * pos_size
        else:
            pnl = (entry_price - current_price) / entry_price * pos_size
        return round(pnl, 4)


# ── GLOBAL INSTANCE ──
risk_guard = RiskGuard()