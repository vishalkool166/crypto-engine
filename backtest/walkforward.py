"""Research-only, leakage-aware per-coin train/holdout comparison.

Uses *dates*, not each candidate's trade count, to split the market. The
last 4h candle from a training trade must close strictly before the split;
research.engine enforces a conservative exit/entry embargo. Do not optimize
against holdout results and do not auto-promote a parameter set into live code.

Usage (requires complete, checksum-verified candles and funding):
  python -m backtest.walkforward --data-dir research_data \
    --train-start 2023-01-01 --split 2025-01-01 --end 2026-10-01
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from datetime import datetime, timezone
from pandas import Timestamp, DateOffset

from config import COIN_CONFIG
from backtest.per_coin_audit import variants, research_override
from backtest.research import evaluate

MIN_TRAIN_TRADES = 30
MIN_TEST_TRADES = 15


def _compact(result: dict) -> dict:
    fields = ('total_trades', 'total_signals', 'win_rate', 'expectancy',
              'profit_factor', 'max_drawdown', 'total_return', 'total_pnl',
              'signals_per_30d', 'fills_per_30d', 'funding_modeled')
    if result.get('error'):
        return {'error': result['error']}
    return {key: result.get(key) for key in fields}


def eligible_training(result: dict) -> bool:
    """Necessary, NOT sufficient evidence. Never evaluates a holdout metric."""
    return (
        'error' not in result and result.get('funding_modeled') is True
        and result.get('total_trades', 0) >= MIN_TRAIN_TRADES
        and math.isfinite(float(result.get('expectancy', 0)))
        and float(result['expectancy']) > 0
        and result.get('profit_factor') is not None
        and float(result['profit_factor']) > 1.0
    )


def validate_dates(train_start: str, split: str, end: str) -> None:
    from pandas import Timestamp
    times = [Timestamp(v) for v in (train_start, split, end)]
    times = [t.tz_localize('UTC') if t.tzinfo is None else t.tz_convert('UTC') for t in times]
    if not times[0] < times[1] < times[2]:
        raise ValueError('Research dates must satisfy train_start < split < end')
    if times[1] - times[0] < __import__('pandas').Timedelta(days=180):
        raise ValueError('Training history must cover at least 180 calendar days')
    if times[2] - times[1] < __import__('pandas').Timedelta(days=90):
        raise ValueError('Holdout must cover at least 90 calendar days')
    if times[2] > Timestamp.now(tz='UTC'):
        raise ValueError('Holdout cannot include incomplete future observations')
    if any(t.hour or t.minute or t.second or t.microsecond for t in times):
        raise ValueError('Use aligned UTC midnight date boundaries')


def audit_coin(coin: str, data_dir: Path, train_start: str, split: str, end: str) -> dict:
    if coin not in COIN_CONFIG:
        raise ValueError(f'Coin is not configured: {coin}')
    validate_dates(train_start, split, end)
    original = COIN_CONFIG[coin].copy()
    training = {}
    eligible = []
    # Train only. Each candidate is evaluated against an identical wall-clock
    # period, not an individually chosen profitable set of trade dates.
    for name, override in variants(coin).items():
        with research_override(coin, override):
            result = evaluate(coin, data_dir, signal_start=train_start, signal_end=split)
        training[name] = _compact(result)
        if eligible_training(result):
            eligible.append((float(result['expectancy']), name))
    # Fail closed to the frozen config when no reliable variant emerges.
    chosen = max(eligible, key=lambda pair: pair[0])[1] if eligible else 'configured'
    chosen_override = variants(coin)[chosen]
    with research_override(coin, chosen_override):
        tested = evaluate(coin, data_dir, signal_start=split, signal_end=end)
    test = _compact(tested)
    enough_holdout = 'error' not in tested and tested.get('total_trades', 0) >= MIN_TEST_TRADES
    positive_holdout = enough_holdout and tested.get('profit_factor') is not None and (
        tested['expectancy'] > 0 and tested['profit_factor'] > 1
    )
    return {
        'coin': coin, 'frozen_original_config': original,
        'train_start': train_start, 'split': split, 'holdout_end': end,
        'training_variants': training, 'training_selected': chosen,
        'holdout': test,
        'assessment': ('RESEARCH_ONLY_POSITIVE_HOLDOUT_NOT_VERIFIED_FOR_LIVE'
                       if positive_holdout else 'NO_VERIFIED_EDGE'),
        'limitations': [
            'No variant promoted automatically to live',
            'Many coins and parameter variants require multiple-testing correction',
            'Positive holdout alone is not proof of predictive profitability',
            'Entry and stop fills are OHLC approximations, not orderbook executions',
            'Ranges are descriptive: live range strategy remains disabled',
        ],
    }


def rolling_periods(start: str, end: str, train_months: int = 12,
                    test_months: int = 3) -> list[tuple[str, str, str]]:
    """Expanding training window, contiguous non-overlapping test quarters."""
    if train_months < 6 or test_months < 3:
        raise ValueError('Require >=6 months training and >=3 months test periods')
    start_ts, end_ts = Timestamp(start), Timestamp(end)
    if start_ts.tzinfo is None:
        start_ts = start_ts.tz_localize('UTC')
    if end_ts.tzinfo is None:
        end_ts = end_ts.tz_localize('UTC')
    if not start_ts < end_ts <= Timestamp.now(tz='UTC'):
        raise ValueError('Invalid research window')
    split = start_ts + DateOffset(months=train_months)
    periods = []
    while split + DateOffset(months=test_months) <= end_ts:
        stop = split + DateOffset(months=test_months)
        validate_dates(str(start_ts), str(split), str(stop))
        periods.append((start_ts.strftime('%Y-%m-%d'), split.strftime('%Y-%m-%d'),
                        stop.strftime('%Y-%m-%d')))
        split = stop
    if not periods:
        raise ValueError('Not enough history for a completed training+test fold')
    return periods


def rolling_audit_coin(coin: str, data_dir: Path, start: str, end: str,
                       train_months: int = 12, test_months: int = 3) -> dict:
    periods = rolling_periods(start, end, train_months, test_months)
    folds = [audit_coin(coin, data_dir, *period) for period in periods]
    # No averaging percentage returns across unequal periods or claiming
    # independent evidence from folds that reuse expanding training history.
    return {
        'coin': coin, 'validation': 'expanding_window_rolling_holdouts',
        'folds': folds, 'positive_folds': sum(
            item['assessment'].startswith('RESEARCH_ONLY_POSITIVE') for item in folds
        ),
        'total_folds': len(folds),
        'status': 'RESEARCH_ONLY_NOT_APPROVED_FOR_LIVE',
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--coins', default=','.join(COIN_CONFIG))
    parser.add_argument('--data-dir', default='research_data')
    parser.add_argument('--train-start', required=True)
    parser.add_argument('--split')
    parser.add_argument('--rolling', action='store_true')
    parser.add_argument('--train-months', type=int, default=12)
    parser.add_argument('--test-months', type=int, default=3)
    parser.add_argument('--end', required=True)
    parser.add_argument('--output', default='research_data/walkforward_results.json')
    args = parser.parse_args()
    if args.rolling:
        rolling_periods(args.train_start, args.end, args.train_months, args.test_months)
    elif args.split:
        validate_dates(args.train_start, args.split, args.end)
    else:
        parser.error('--split is mandatory unless --rolling is enabled')
    output = []
    for coin in (x.strip().upper() for x in args.coins.split(',') if x.strip()):
        try:
            if args.rolling:
                result = rolling_audit_coin(coin, Path(args.data_dir),
                                            args.train_start, args.end,
                                            args.train_months, args.test_months)
            else:
                result = audit_coin(coin, Path(args.data_dir), args.train_start,
                                    args.split, args.end)
        except Exception as error:
            result = {'coin': coin, 'assessment': 'NOT_EVALUATED', 'error': str(error)}
        output.append(result)
        print(coin, result.get('assessment', result.get('status', 'NOT_EVALUATED')))
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({'generated_utc': datetime.now(timezone.utc).isoformat(),
                                   'results': output}, indent=2) + '\n')
    print('Saved:', target)


if __name__ == '__main__':
    main()
