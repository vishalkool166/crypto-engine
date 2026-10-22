"""Versioned simulation using CLOSED 4h cached candles; no exchange orders.

Candle-close signal -> next candle open entry. Stops before profit targets on
ambiguous OHLC bars. Ignores unclosed trades. Funding is not modeled, so runs
are NOT execution-quality certification and do not themselves authorize real orders.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
import hashlib
import json
import math
from datetime import datetime, timezone

import pandas as pd
from strategies.registry import MIN_BARS, STRATEGIES, STRATEGY_RELEASE, features, evaluate

ROUND_TRIP_TAKER_FEE = 0.001
ONE_WAY_SLIPPAGE = 0.0004


def run_replay(frame: pd.DataFrame, strategy: str, params: dict | None = None, *, capital: float = 1000.0, risk_fraction: float = .005, max_bars: int = 12) -> dict:
    if strategy not in STRATEGIES or not 0 < risk_fraction <= .01 or not 1 <= max_bars <= 30:
        raise ValueError("Invalid bounded research configuration")
    d = features(frame)
    # Date-based chronological split, no training optimization or data tuning.
    split = MIN_BARS + int((len(d)-MIN_BARS) * .65)
    if split + 10 >= len(d):
        raise ValueError("Need more complete candles after indicator warmup")
    params = params or {}
    value, peak = float(capital), float(capital)
    if not math.isfinite(value) or value <= 0:
        raise ValueError("Capital must be positive")
    trades, rejections = [], {}
    cursor = MIN_BARS
    while cursor < len(d)-1:
        past = d.iloc[:cursor+1]
        event = evaluate(past, strategy, params)
        if not event["candidate"]:
            reason = event["rejection"]
            rejections[reason] = rejections.get(reason,0) + 1
            cursor += 1
            continue
        c = event["candidate"]
        next_open = float(d.open.iloc[cursor+1])
        sign = 1 if c["direction"] == "LONG" else -1
        entry = next_open * (1 + sign * ONE_WAY_SLIPPAGE)
        # Reject if next opening gap invalidates the pre-committed stop/target.
        if (sign * (entry-c["stop"]) <= 0 or sign * (c["target"]-entry) <= 0):
            rejections["gap_invalidated_levels"] = rejections.get("gap_invalidated_levels",0)+1
            cursor += 1
            continue
        risk_unit = abs(entry - c["stop"])
        quantity = min(value * risk_fraction / risk_unit, value / entry)  # 1x notional cap
        if quantity <= 0:
            break
        last_bar = min(cursor + max_bars, len(d)-1)
        closed = False
        for j in range(cursor+1, last_bar+1):
            high, low, close = map(float,(d.high.iloc[j],d.low.iloc[j],d.close.iloc[j]))
            stop_hit = low <= c["stop"] if sign > 0 else high >= c["stop"]
            target_hit = high >= c["target"] if sign > 0 else low <= c["target"]
            if stop_hit or target_hit or j == last_bar and j < len(d)-1:
                if stop_hit:
                    # Stop-market orders can slip across an adverse opening gap.
                    bar_open = float(d.open.iloc[j])
                    exit_price = min(c["stop"], bar_open) if sign > 0 else max(c["stop"], bar_open)
                    why = "stop_or_ambiguous"
                elif target_hit:
                    exit_price, why = c["target"], "target"
                else:
                    exit_price, why = close, "time"
                exit_price *= (1-sign*ONE_WAY_SLIPPAGE)
                gross = (exit_price-entry)*sign*quantity
                fee = (entry+exit_price)*quantity*(ROUND_TRIP_TAKER_FEE/2)
                net = gross-fee
                # A development trade cannot close inside the sealed holdout.
                # Embargo boundary-crossing trades from both evaluation sets.
                if cursor < split <= j:
                    rejections["holdout_boundary_embargo"] = rejections.get("holdout_boundary_embargo",0)+1
                    cursor = j+1
                    closed = True
                    break
                value += net
                peak = max(peak, value)
                trades.append({"signal_at":str(d.index[cursor]),"entry_at":str(d.index[cursor+1]),"exit_at":str(d.index[j]),"direction":c["direction"],"entry":round(entry,6),"exit":round(exit_price,6),"stop":round(c["stop"],6),"target":round(c["target"],6),"reason":why,"net_pnl":round(net,6),"fees":round(fee,6),"regime":c["regime"],"segment":"holdout" if cursor >= split else "development","drawdown_pct":round((value/peak-1)*100,3)})
                cursor = j+1
                closed = True
                break
        if not closed:
            # Unresolved final trade is not treated as a win or forced exit.
            rejections["open_at_data_end"] = rejections.get("open_at_data_end",0)+1
            break
        if value <= 0:
            break
    def metric(rows):
        profits = [t["net_pnl"] for t in rows if t["net_pnl"]>0]
        losses = [t["net_pnl"] for t in rows if t["net_pnl"]<0]
        # Independent high-water mark for each evaluation period.
        equity_curve = [1000.]
        for trade in rows:
            equity_curve.append(equity_curve[-1] + trade["net_pnl"])
        highwater = equity_curve[0]
        worst_dd = 0.
        for equity in equity_curve:
            highwater = max(highwater,equity)
            worst_dd = min(worst_dd,(equity/highwater - 1)*100)
        return {"trades":len(rows),"wins":len(profits),"win_rate_pct":round(100*len(profits)/len(rows),2) if rows else None,"net_pnl_usdt":round(sum(t["net_pnl"] for t in rows),4),"net_expectancy_usdt":round(sum(t["net_pnl"] for t in rows)/len(rows),4) if rows else None,"profit_factor":round(sum(profits)/abs(sum(losses)),3) if losses else None,"max_drawdown_pct":round(worst_dd,2)}
    development = [t for t in trades if t["segment"]=="development"]
    holdout = [t for t in trades if t["segment"]=="holdout"]
    clean_data = frame.loc[:,["open","high","low","close","volume"]].astype(float)
    fingerprint = hashlib.sha256(pd.util.hash_pandas_object(clean_data,index=True).values.tobytes()).hexdigest()
    result={"strategy":strategy,"version":STRATEGY_RELEASE,"parameters":params,"data_sha256":fingerprint,"bars":len(d),"first_bar":str(d.index[0]),"last_bar":str(d.index[-1]),"holdout_from":str(d.index[split]),"development":metric(development),"holdout":metric(holdout),"all_trades":len(trades),"ending_equity":round(value,4),"simulated":True,"funding_modeled":False,"status":"RESEARCH_ONLY_UNCERTIFIED","limitations":["Cached candles are capped by the main application; not a multi-year study","The split is descriptive and does not tune parameters; this is not walk-forward certification","Funding, liquidity and exchange-specific liquidation are not modeled","Ambiguous OHLC stop/target bars are counted as stops","Live orders require the shared risk/execution safeguards and explicit account-level live authorization"],"rejection_counts":rejections,"trades":trades}
    return result


def run_cached(coin: str, strategy: str, params: dict | None = None) -> dict:
    from data.store import load_candles
    data = load_candles(coin, "4h", limit=350)
    if data is None or len(data) < 260:
        raise ValueError("Insufficient cached closed 4h candles (minimum 260); run the existing data scanner first")
    return run_replay(data, strategy, params)
