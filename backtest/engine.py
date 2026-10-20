"""Research-only replay of the live crypto decision pipeline.

No broker calls or trades. OHLCV bar timestamps MUST denote their OPEN time in UTC.
A setup formed on a completed 4h bar can only enter during the following bar.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import math

import pandas as pd

from config import cfg, get_coin_config, TAKER_FEE

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReplayCosts:
    entry_fee: float = TAKER_FEE
    exit_fee: float = TAKER_FEE
    entry_slippage_bps: float = 3.0
    exit_slippage_bps: float = 3.0
    max_holding_bars: int = 40
    entry_expiry_bars: int = 1  # Live limit expires after 4h.
    risk_fraction: float = 0.005
    max_margin_fraction: float = 0.20
    max_leverage: int = 10


def _utc_index(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return frame
    df = frame.copy()
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError('Candle index must be datetime (open timestamps)')
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC')
    else:
        df.index = df.index.tz_convert('UTC')
    if not df.index.is_monotonic_increasing or df.index.has_duplicates:
        raise ValueError('Candles must be strictly increasing without duplicates')
    values = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
    if not values.notna().all().all() or not values.map(math.isfinite).all().all():
        raise ValueError('Candle data contains missing or non-finite prices')
    if (values[['open', 'high', 'low', 'close']] <= 0).any().any() or (values['volume'] < 0).any():
        raise ValueError('Invalid candle prices or volume')
    if ((values['high'] < values[['open', 'close']].max(axis=1)) |
        (values['low'] > values[['open', 'close']].min(axis=1))).any():
        raise ValueError('Inconsistent candle OHLC')
    return df


def _session_matches(coin: str, timestamp: pd.Timestamp) -> bool:
    """Identical session classification to live sizing on the signal timestamp."""
    from engines.core.sessions import session_matches
    return session_matches(get_coin_config(coin).get('session', 'all'), timestamp)


def _simulate_trade(
    df: pd.DataFrame, current_i: int, direction: str, entry: float,
    sl: float, tp1: float, tp2: float | None = None,
    *, costs: ReplayCosts | None = None,
) -> dict:
    """Conservative OHLC limit-entry simulation, full closure at TP1 as live does.

    Intrabar ordering is unknown: stop takes precedence over target. We do not
    assume unfilled limit orders execute. Post-stop gap/slippage is not guaranteed
    to be this small in reality. TP2 is an informational live field, not an exit.
    """
    costs = costs or ReplayCosts()
    if direction not in ('LONG', 'SHORT') or not (entry > 0 and sl > 0 and tp1 > 0):
        raise ValueError('Invalid trade setup')
    if not ((sl < entry < tp1) if direction == 'LONG' else (tp1 < entry < sl)):
        raise ValueError('Stop/target on wrong side of entry')
    is_long = direction == 'LONG'
    end = min(len(df), current_i + costs.entry_expiry_bars)
    fill_i = None
    for i in range(current_i, end):
        bar = df.iloc[i]
        if float(bar['low']) <= entry <= float(bar['high']):
            fill_i = i
            break
    if fill_i is None:
        return {'outcome': 'no_fill', 'exit_price': None, 'candles': 0,
                'tp1_hit': False, 'tp2_hit': False, 'exit_i': current_i,
                'fill_i': None}

    max_i = min(len(df), fill_i + costs.max_holding_bars)
    for j in range(fill_i, max_i):
        bar = df.iloc[j]
        high, low = float(bar['high']), float(bar['low'])
        # A bar that crosses both the TP and stop is considered a stop-out.
        stopped = low <= sl if is_long else high >= sl
        targeted = high >= tp1 if is_long else low <= tp1
        if stopped:
            # A stop-market order cannot guarantee the stop price after a gap.
            # From later bars onward the first observable price is the open.
            stop_fill = sl
            if j > fill_i:
                opened = float(bar['open'])
                stop_fill = min(sl, opened) if is_long else max(sl, opened)
            return {'outcome': 'loss', 'exit_price': stop_fill, 'candles': j - fill_i + 1,
                    'tp1_hit': False, 'tp2_hit': False, 'exit_i': j,
                    'fill_i': fill_i}
        if targeted:
            # On the entry bar, OHLC cannot establish whether the target was
            # reached before a resting limit order filled. For a buy limit
            # below the opening price (or sell limit above it), don't credit
            # a target that may have preceded entry. Carry the position to
            # the next candle or mark to market at the holding limit.
            target_before_entry_possible = (j == fill_i and
                ((is_long and float(bar['open']) > entry) or
                 (not is_long and float(bar['open']) < entry)))
            if target_before_entry_possible:
                continue
            return {'outcome': 'win', 'exit_price': tp1, 'candles': j - fill_i + 1,
                    'tp1_hit': True, 'tp2_hit': False, 'exit_i': j,
                    'fill_i': fill_i}

    j = max_i - 1
    return {'outcome': 'timeout', 'exit_price': float(df.iloc[j]['close']),
            'candles': max_i - fill_i, 'tp1_hit': False, 'tp2_hit': False,
            'exit_i': j, 'fill_i': fill_i}


def _net_pnl(*, direction: str, entry: float, exit_price: float,
             notional: float, costs: ReplayCosts, funding_rate_sum: float = 0) -> float:
    sign = 1 if direction == 'LONG' else -1
    gross = sign * notional * (exit_price / entry - 1)
    fees = notional * (costs.entry_fee + costs.exit_fee * exit_price / entry)
    slippage = notional * (costs.entry_slippage_bps + costs.exit_slippage_bps) / 10000
    # Positive funding is a payment from longs to shorts.
    funding = sign * notional * funding_rate_sum
    return round(gross - fees - slippage - funding, 6)


def _funding_sum(funding: pd.DataFrame | None, start: pd.Timestamp,
                 end: pd.Timestamp) -> float:
    if funding is None or funding.empty:
        return 0.0
    # Use settlement timestamps, not daily averages, so funding is not leaked.
    mask = (funding.index > start) & (funding.index <= end)
    return float(funding.loc[mask, 'funding_rate'].sum())


def _load_csv(file: str | Path) -> pd.DataFrame:
    df = pd.read_csv(file)
    if 'timestamp' not in df:
        raise ValueError(f'{file}: expected timestamp column')
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    return _utc_index(df.set_index('timestamp'))


def _summary(trades: list[dict], capital: float) -> dict:
    pnls = [t['pnl'] for t in trades]
    wins = sum(p > 0 for p in pnls)
    losses = sum(p < 0 for p in pnls)
    gross_profit = sum(p for p in pnls if p > 0)
    gross_loss = -sum(p for p in pnls if p < 0)
    equity = capital
    peak = capital
    max_dd = 0.0
    for trade in trades:
        equity += trade['pnl']
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak * 100 if peak > 0 else 0)
    return {
        'total_trades': len(trades), 'wins': wins, 'losses': losses,
        'win_rate': round(wins / len(trades) * 100, 2) if trades else 0.0,
        'profit_factor': round(gross_profit / gross_loss, 3) if gross_loss else None,
        'expectancy': round(sum(pnls) / len(pnls), 4) if pnls else 0.0,
        'total_pnl': round(sum(pnls), 4),
        'total_return': round((equity / capital - 1) * 100, 3) if capital else 0,
        'final_equity': round(equity, 4), 'max_drawdown': round(max_dd, 3),
    }


def run_backtest(
    coin: str, capital: float = 1000, leverage: int = 10,
    *, df_4h: pd.DataFrame | None = None, df_1h: pd.DataFrame | None = None,
    costs: ReplayCosts | None = None, funding: pd.DataFrame | None = None,
    persist: bool = True, research_min_score: float = 50.0,
    signal_start: str | pd.Timestamp | None = None,
    signal_end: str | pd.Timestamp | None = None,
) -> dict:
    """Historical research; never submits orders. Default store holds only ~350 bars.

    Pass longer, UTC, open-timestamped dataframes from research CSV datasets for
    meaningful historical research. Does NOT model the full dynamic live sizing,
    portfolio exposure, liquidation, bid/ask queue or impact.
    """
    if not (40 <= research_min_score <= 50):
        raise ValueError('Research score threshold must be between 40 and 50')
    if not capital > 0 or not (1 <= leverage <= 125):
        raise ValueError('Positive capital and valid leverage required')
    from data.store import load_candles
    from engines.core.indicators import get_indicators
    from engines.regime.detector import detect as detect_regime
    from engines.trend.direction import detect as detect_trend
    from engines.scoring.scorer import score as calc_score
    from engines.risk.calculator import calculate as calc_risk

    costs = costs or ReplayCosts()
    df_4h = _utc_index(df_4h if df_4h is not None else load_candles(coin, '4h', limit=2000))
    df_1h = _utc_index(df_1h if df_1h is not None else load_candles(coin, '1h', limit=5000))
    if df_4h is None or len(df_4h) < 260:
        return {'coin': coin, 'error': 'Insufficient 4h history (need >= 260 closed bars)'}
    if df_1h is None or len(df_1h) < 100:
        return {'coin': coin, 'error': 'Insufficient 1h history'}
    if (df_4h.index.to_series().diff().dropna() != pd.Timedelta(hours=4)).any() or \
       (df_1h.index.to_series().diff().dropna() != pd.Timedelta(hours=1)).any():
        return {'coin': coin, 'error': 'Missing candle interval(s); refuse incomplete backtest'}

    def _bound(value):
        if value is None:
            return None
        return pd.Timestamp(value, tz="UTC") if pd.Timestamp(value).tzinfo is None else pd.Timestamp(value).tz_convert("UTC")
    interval_start, interval_end = _bound(signal_start), _bound(signal_end)
    if interval_start is not None and interval_end is not None and interval_start >= interval_end:
        raise ValueError("signal_start must precede signal_end")
    # Independent validation windows must never trade an exit beyond their
    # end boundary. The embargo equals the maximum simulated hold+entry wait.
    embargo = pd.Timedelta(hours=4 * (costs.max_holding_bars + costs.entry_expiry_bars))
    # Dataset truncation is also an evaluation boundary: never score a trade
    # whose maximum time in market cannot be observed. This matters even when
    # no explicit train/test window was supplied.
    available_until = df_4h.index[-1] + pd.Timedelta(hours=4)
    evaluation_until = min(available_until, interval_end) if interval_end is not None else available_until
    evaluation_start = max(df_4h.index[220], interval_start) if interval_start is not None else df_4h.index[220]
    last_eligible_signal = evaluation_until - embargo
    observed_days = max(0.0, (last_eligible_signal - evaluation_start).total_seconds() / 86400)

    trades = []
    rejection_counts: dict[str, int] = {}
    def reject(reason: str) -> None:
        rejection_counts[reason] = rejection_counts.get(reason, 0) + 1

    equity = capital
    i = 220
    loss_pause_until = None
    considered = 0
    signal_count = 0
    while i < len(df_4h):
        signal_ts = df_4h.index[i]  # just after preceding 4h candle closes
        if interval_start is not None and signal_ts < interval_start:
            i += 1
            continue
        if signal_ts > last_eligible_signal:
            break
        if loss_pause_until is not None and signal_ts < loss_pause_until:
            i += 1
            continue
        if not _session_matches(coin, signal_ts):
            reject('session')
            i += 1
            continue
        window_4h = df_4h.iloc[i - 220:i]
        window_1h = df_1h[df_1h.index < signal_ts].tail(220)
        if len(window_1h) < 200:
            i += 1
            continue
        considered += 1
        d4h = get_indicators(window_4h, timeframe='4h')
        d1h = get_indicators(window_1h, timeframe='1h')
        if any(not math.isfinite(float(d4h.get(k, 0))) or float(d4h.get(k, 0)) <= 0
               for k in ('price', 'ema200', 'atr')):
            reject('invalid_indicators')
            i += 1
            continue
        regime = detect_regime(d4h)
        if regime.is_volatile:
            reject('volatile_regime')
            i += 1
            continue
        trend = detect_trend(d4h, coin, record_rejection=False)
        if not trend.passed:
            reject(trend.reason)
            i += 1
            continue
        direction = trend.direction
        adx = float(d4h['adx'])
        rsi = float(d1h.get('rsi') or d4h.get('rsi') or 50)
        vol_ratio = float(d4h.get('vol_ratio') or 1)
        grade = calc_score(adx, rsi, vol_ratio, direction, regime.label)
        if grade.grade == 'F' and grade.total < research_min_score:
            reject('grade_f')
            i += 1
            continue
        # Live scanner only persists A and A+ signals. Count B (or relaxed F)
        # trades only when explicitly exploring the research-only relaxation.
        if research_min_score == 50 and grade.grade not in cfg.MIN_GRADE_TO_TRADE:
            reject('live_grade_publish_filter')
            i += 1
            continue
        research_grade = grade.grade if grade.grade != 'F' else 'B'
        risk = calc_risk(direction=direction, entry=d4h['price'],
                         swing_level=d4h['swing_low'] if direction == 'LONG' else d4h['swing_high'],
                         atr=d4h['atr'], coin=coin)
        if not risk.valid:
            reject(risk.reason)
            i += 1
            continue
        if equity <= 0:
            reject('capital_depleted')
            break
        signal_count += 1
        sim = _simulate_trade(df_4h, i, direction, risk.entry, risk.sl, risk.tp1,
                              risk.tp2, costs=costs)
        if sim['outcome'] == 'no_fill':
            reject('limit_not_filled')
            i += 1
            continue
        fill_i = sim['fill_i']
        exit_i = sim['exit_i']
        sl_fraction = abs(risk.entry - risk.sl) / risk.entry
        allowed_risk = equity * costs.risk_fraction * regime.size_mult
        notional = min(allowed_risk / sl_fraction,
                       equity * costs.max_margin_fraction * min(leverage, costs.max_leverage))
        if notional < 5:
            reject('too_small_position')
            i += 1
            continue
        settle_start = df_4h.index[fill_i]
        settle_end = df_4h.index[exit_i] + pd.Timedelta(hours=4)
        funding_sum = _funding_sum(funding, settle_start, settle_end)
        pnl = _net_pnl(direction=direction, entry=risk.entry,
                       exit_price=sim['exit_price'], notional=notional,
                       costs=costs, funding_rate_sum=funding_sum)
        equity += pnl
        trades.append({
            'date': str(signal_ts.date()), 'timestamp': signal_ts.isoformat(),
            'coin': coin, 'grade': research_grade, 'direction': direction,
            'entry': risk.entry, 'sl': risk.sl, 'tp1': risk.tp1,
            'exit': sim['exit_price'], 'exit_timestamp': settle_end.isoformat(),
            'outcome': 'win' if pnl > 0 else 'loss' if pnl < 0 else 'flat',
            'exit_reason': sim['outcome'], 'pnl': pnl,
            'notional': round(notional, 2), 'equity': round(equity, 4),
            'tp1_hit': sim['tp1_hit'], 'tp2_hit': False,
            'regime': regime.label, 'funding_rate_sum': funding_sum,
        })
        if pnl < 0 and get_coin_config(coin).get('skip_after_loss'):
            loss_pause_until = settle_end + pd.Timedelta(hours=48)
        i = exit_i + 1  # forbid overlapping positions in the same coin

    if not trades:
        return {'coin': coin, 'error': 'No completed trades in the sample',
                'total_signals': signal_count, 'total_trades': 0,
                'considered': considered, 'rejections': rejection_counts,
                'eligible_window_start': evaluation_start.isoformat(),
                'eligible_window_end': last_eligible_signal.isoformat()}

    metrics = _summary(trades, capital)
    grades = {}
    for level in ('A+', 'A', 'B'):
        subset = [t for t in trades if t['grade'] == level]
        grades[level] = _summary(subset, capital)
    cut = int(len(trades) * 0.7)
    # This is chronological holdout reporting, not parameter optimization.
    holdout = {
        'method': 'chronological_descriptive_split_70_30_no_tuning',
        'train': _summary(trades[:cut], capital),
        'holdout': _summary(trades[cut:], capital),
    }
    report = {
        **metrics,
        'result_type': 'simulated_backtest',
        'pnl_provenance': 'simulated_not_exchange_realized',
        'exchange_verified': False,
        'coin': coin, 'period_start': trades[0]['date'], 'period_end': trades[-1]['date'],
        'capital': capital, 'total_signals': signal_count,
        'aplus_signals': grades['A+']['total_trades'],
        'a_signals': grades['A']['total_trades'],
        'best_trade': round(max(t['pnl'] for t in trades), 4),
        'worst_trade': round(min(t['pnl'] for t in trades), 4),
        'avg_trade': metrics['expectancy'],
        'by_grade': grades, 'trades': trades, 'walk_forward': holdout,
        'considered': considered, 'rejections': rejection_counts,
        'cost_model': vars(costs), 'funding_modeled': funding is not None,
        'research_min_score': research_min_score,
        'signal_start': interval_start.isoformat() if interval_start is not None else None,
        'signal_end': interval_end.isoformat() if interval_end is not None else None,
        'live_rules_compatible': research_min_score == 50,
        'signals_per_30d': round(signal_count * 30 / observed_days, 2) if observed_days > 0 else 0.0,
        'fills_per_30d': round(len(trades) * 30 / observed_days, 2) if observed_days > 0 else 0.0,
        'eligible_window_start': evaluation_start.isoformat(),
        'eligible_window_end': last_eligible_signal.isoformat(),
        'phase_breakdown': {
            'tp1_hit_rate': round(sum(t['tp1_hit'] for t in trades) / len(trades) * 100, 2),
            'tp2_hit_rate': 0.0,
        },
        'limitations': ['Limit fill inferred from OHLC, not orderbook queue',
                        'Worst-first OHLC stop/TP ordering',
                        'Simple fixed risk sizing, not full live portfolio circuit breaker',
                        'No liquidation, exchange downtime, or market-impact model',
                        'Research score <50 is hypothetical and not enabled in live trading'],
    }
    if persist:
        # Current DB schema has only summary columns; do not silently store partial
        # results if the reporting adapter expects fields absent from the report.
        from backtest.report import _save_to_db
        _save_to_db(report, coin)
    return report
