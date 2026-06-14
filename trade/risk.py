from config import cfg
from database import SessionLocal, Trade, DailyRisk
from datetime import datetime, timezone
import logging

log = logging.getLogger(__name__)

_cap_warning_sent = False


def dynamic_risk_pct(score: float) -> float:
    min_risk = 0.07
    max_risk = 0.13
    base     = 0.10

    if score >= 95:
        return max_risk
    if score >= 85:
        t = (score - 85) / 10
        return round(base + t * (max_risk - base), 3)
    if score >= 68:
        t = (score - 68) / 17
        return round(min_risk + t * (base - min_risk), 3)
    return min_risk


def get_tier_config(balance: float) -> dict:
    for i, tier in enumerate(cfg.BALANCE_TIERS, 1):
        if tier["max"] is None or balance < tier["max"]:
            return {
                "tier":       i,
                "risk_pct":   tier["risk_pct"],
                "max_trades": tier["max_trades"],
                "leverage":   tier["leverage"],
                "balance":    balance
            }
    return {
        "tier":       4,
        "risk_pct":   0.12,
        "max_trades": 3,
        "leverage":   20,
        "balance":    balance
    }


def get_current_tier() -> dict:
    import runtime_state as rs
    cached = rs.get_balance_cache()
    bal    = cached.get("balance", cfg.CAPITAL)
    if bal <= 0:
        bal = cfg.CAPITAL
    return get_tier_config(bal)


class RiskGuard:

    def calculate_position(
        self,
        entry:      float,
        sl:         float,
        capital:    float = None,
        leverage:   int   = None,
        confidence: float = 85.0
    ) -> dict:
        tier     = get_current_tier()
        capital  = capital  or tier["balance"] or cfg.CAPITAL
        leverage = leverage or tier["leverage"]

        sl_dist = abs(entry - sl)
        sl_pct  = sl_dist / entry

        if sl_pct == 0:
            return {"valid": False, "reason": "SL equals entry"}

        risk_pct = dynamic_risk_pct(confidence)
        risk_amt = capital * risk_pct
        pos_size = risk_amt / sl_pct
        margin   = pos_size / leverage

        if margin > capital:
            return {"valid": False, "reason": f"Margin ${margin:.2f} exceeds capital ${capital:.2f}"}

        if risk_amt < 0.10:
            return {"valid": False, "reason": f"Risk amount ${risk_amt:.2f} too small"}

        fee_entry = pos_size * 0.0006
        fee_exit  = pos_size * 0.0006
        total_fee = fee_entry + fee_exit
        net_risk  = risk_amt - total_fee

        if net_risk <= 0:
            return {"valid": False, "reason": f"Fees ${total_fee:.4f} exceed risk ${risk_amt:.2f}"}

        return {
            "valid":      True,
            "risk_pct":   risk_pct,
            "risk_amt":   round(risk_amt, 4),
            "pos_size":   round(pos_size, 4),
            "margin":     round(margin, 4),
            "sl_pct":     round(sl_pct * 100, 4),
            "fee_est":    round(total_fee, 4),
            "net_risk":   round(net_risk, 4),
            "leverage":   leverage,
            "confidence": confidence
        }

    def pre_trade_check(self, signal: dict, capital: float = None) -> dict:
        reasons = []
        tier    = get_current_tier()
        capital = capital or tier["balance"] or cfg.CAPITAL

        if signal.get("grade") not in cfg.MIN_GRADE_TO_TRADE:
            reasons.append(f"Grade {signal.get('grade')} below minimum")

        if signal.get("direction") not in ["LONG", "SHORT"]:
            reasons.append(f"Invalid direction: {signal.get('direction')}")

        if cfg.REQUIRE_SWEEP_OR_DISPLACEMENT:
            sweep_ok = signal.get("sweep_score", 0) >= 6
            disp_ok  = signal.get("disp_score",  0) >= 6
            if not sweep_ok and not disp_ok:
                reasons.append("Neither sweep nor displacement confirmed")

        funding = signal.get("funding", 0) * 100
        if abs(funding) > 0.08:
            reasons.append(f"Extreme funding {funding:.4f}%")

        exposure_check = self.check_exposure(signal.get("coin", ""), capital)
        if not exposure_check["allowed"]:
            reasons.append(exposure_check["reason"])

        confidence = signal.get("score", 85.0)
        sizing     = self.calculate_position(
            entry      = signal.get("entry", 0),
            sl         = signal.get("sl", 0),
            capital    = capital,
            confidence = confidence
        )
        if not sizing["valid"]:
            reasons.append(f"Sizing failed: {sizing['reason']}")

        if reasons:
            return {"allowed": False, "reasons": reasons, "sizing": None}

        return {"allowed": True, "reasons": [], "sizing": sizing}

    def check_exposure(self, coin: str, capital: float = None) -> dict:
        try:
            from trade.state import state_manager
            tier    = get_current_tier()
            capital = capital or tier["balance"] or cfg.CAPITAL

            active = state_manager.active_trades
            if not active:
                return {"allowed": True, "reason": ""}

            if coin and any(t.coin == coin for t in active.values()):
                return {"allowed": False, "reason": f"{coin} already has open trade"}

            if coin != "BTC" and any(t.coin == "BTC" for t in active.values()):
                return {"allowed": False, "reason": "BTC trade active — altcoin entries blocked"}

            total_exposure = sum(t.position_size or 0 for t in active.values())
            max_exposure   = capital * tier["leverage"] * 0.8
            if total_exposure >= max_exposure:
                return {"allowed": False, "reason": f"Total exposure ${total_exposure:.2f} at limit"}

        except Exception as e:
            log.warning(f"Exposure check error: {e}")

        return {"allowed": True, "reason": ""}

    def get_daily_stats(self) -> dict:
        db    = SessionLocal()
        today = str(datetime.now(timezone.utc).date())
        try:
            risk       = db.query(DailyRisk).filter(DailyRisk.date == today).first()
            tier       = get_current_tier()
            capital    = tier["balance"] or cfg.CAPITAL
            daily_cap  = capital * cfg.DAILY_LOSS_CAP_PCT
            max_trades = tier["max_trades"]

            if not risk:
                return {
                    "date":             today,
                    "trades_taken":     0,
                    "total_pnl":        0.0,
                    "total_loss":       0.0,
                    "cap_hit":          False,
                    "remaining_trades": max_trades,
                    "remaining_loss":   daily_cap,
                    "approaching_cap":  False
                }

            loss_used_pct = abs(risk.total_loss) / daily_cap * 100 if daily_cap > 0 else 0
            approaching   = loss_used_pct >= 80 and not risk.cap_hit

            if approaching:
                self._warn_approaching_cap(risk.total_loss, daily_cap)

            return {
                "date":             today,
                "trades_taken":     risk.trades_taken,
                "total_pnl":        round(risk.total_pnl, 4),
                "total_loss":       round(risk.total_loss, 4),
                "cap_hit":          risk.cap_hit,
                "remaining_trades": max(0, max_trades - risk.trades_taken),
                "remaining_loss":   round(max(0, daily_cap - abs(risk.total_loss)), 4),
                "approaching_cap":  approaching
            }
        finally:
            db.close()

    def _warn_approaching_cap(self, total_loss: float, daily_cap: float):
        global _cap_warning_sent
        if _cap_warning_sent:
            return
        _cap_warning_sent = True
        try:
            import asyncio
            pct = abs(total_loss) / daily_cap * 100
            asyncio.create_task(self._send_cap_warning(pct, total_loss, daily_cap))
        except Exception:
            pass

    async def _send_cap_warning(self, pct: float, total_loss: float, daily_cap: float):
        try:
            from alerts.telegram import send
            await send(
                f"⚠️ *Daily Loss Cap Warning*\n\n"
                f"Loss used: `{pct:.1f}%` of daily cap\n"
                f"Lost today: `${abs(total_loss):.4f}`\n"
                f"Cap limit:  `${daily_cap:.4f}`\n"
                f"Remaining:  `${daily_cap - abs(total_loss):.4f}`\n\n"
                f"_One more loss may hit the cap._"
            )
        except Exception:
            pass

    def calculate_unrealized_pnl(
        self,
        direction:     str,
        entry_price:   float,
        current_price: float,
        pos_size:      float
    ) -> float:
        if direction == "LONG":
            pnl = (current_price - entry_price) / entry_price * pos_size
        else:
            pnl = (entry_price - current_price) / entry_price * pos_size
        return round(pnl, 4)

    def record_trade_open(self):
        today = str(datetime.now(timezone.utc).date())
        tier  = get_current_tier()
        try:
            with SessionLocal() as db:
                risk = db.query(DailyRisk).filter(DailyRisk.date == today).first()
                if not risk:
                    risk = DailyRisk(
                        date         = today,
                        trades_taken = 1,
                        total_pnl    = 0.0,
                        total_loss   = 0.0,
                        cap_hit      = False,
                        tier         = tier["tier"]
                    )
                    db.add(risk)
                else:
                    risk.trades_taken += 1
        except Exception as e:
            log.error(f"record_trade_open error: {e}")

    def record_partial_pnl(self, pnl: float):
        today = str(datetime.now(timezone.utc).date())
        tier  = get_current_tier()
        try:
            with SessionLocal() as db:
                risk = db.query(DailyRisk).filter(DailyRisk.date == today).first()
                if not risk:
                    risk = DailyRisk(
                        date         = today,
                        trades_taken = 0,
                        total_pnl    = 0.0,
                        total_loss   = 0.0,
                        cap_hit      = False,
                        tier         = tier["tier"]
                    )
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
        global _cap_warning_sent
        _cap_warning_sent = False

        today = str(datetime.now(timezone.utc).date())
        tier  = get_current_tier()
        try:
            with SessionLocal() as db:
                risk = db.query(DailyRisk).filter(DailyRisk.date == today).first()
                if not risk:
                    risk = DailyRisk(
                        date         = today,
                        trades_taken = 0,
                        total_pnl    = 0.0,
                        total_loss   = 0.0,
                        cap_hit      = False,
                        tier         = tier["tier"]
                    )
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


risk_guard = RiskGuard()