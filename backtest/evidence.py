"""Fail-closed evidence gate for saved walk-forward results (never deploys a strategy).

This is a completeness gate, NOT statistical certification or live approval.
Reports are derived from locally verified research data when available.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from config import COIN_CONFIG


def _valid_holdout(fold: dict) -> tuple[bool, str]:
    holdout = fold.get('holdout')
    if not isinstance(holdout, dict) or holdout.get('error'):
        return False, 'missing_or_failed_holdout'
    try:
        trades = int(holdout['total_trades'])
        expectancy = float(holdout['expectancy'])
        profit_factor = float(holdout['profit_factor'])
        net_pnl = float(holdout['total_pnl'])
        drawdown = float(holdout['max_drawdown'])
        win_rate = float(holdout['win_rate'])
        total_signals = int(holdout['total_signals'])
        frequencies = [float(holdout['signals_per_30d']), float(holdout['fills_per_30d'])]
    except (KeyError, ValueError, TypeError, OverflowError):
        return False, 'missing_metrics'
    if holdout.get('funding_modeled') is not True:
        return False, 'funding_unverified'
    if trades < 15:
        return False, 'insufficient_holdout_trades'
    if not all(math.isfinite(v) and v >= 0 for v in frequencies):
        return False, 'invalid_signal_frequency'
    if not all(math.isfinite(v) for v in (expectancy, profit_factor, net_pnl, drawdown, win_rate)):
        return False, 'nonfinite_metrics'
    if not (0 <= drawdown <= 100 and 0 <= win_rate <= 100 and total_signals >= trades):
        return False, 'inconsistent_metrics'
    if expectancy <= 0 or profit_factor <= 1 or net_pnl <= 0:
        return False, 'nonpositive_net_edge'
    return True, 'descriptively_positive_not_live_approved'


def assess(results: list[dict], required_coins: tuple[str, ...] | None = None) -> dict:
    required = tuple(required_coins or tuple(COIN_CONFIG))
    actual = {}
    for item in results:
        if not isinstance(item, dict):
            raise ValueError('Expected a list of per-coin objects')
        coin = item.get('coin')
        if coin in actual:
            raise ValueError(f'Duplicate coin in report: {coin!r}')
        actual[coin] = item

    assessments = []
    for coin in required:
        item = actual.get(coin)
        if not item or item.get('validation') != 'expanding_window_rolling_holdouts':
            assessments.append({'coin': coin, 'status': 'NOT_EVALUATED',
                                'reason': 'missing_or_incompatible_rolling_report'})
            continue
        folds = item.get('folds')
        if not isinstance(folds, list) or len(folds) < 2 or item.get('total_folds') != len(folds):
            assessments.append({'coin': coin, 'status': 'INSUFFICIENT_EVIDENCE',
                                'reason': 'need_at_least_two_valid_folds'})
            continue
        reasons = [_valid_holdout(fold) for fold in folds]
        accepted = all(status for status, _ in reasons)
        assessments.append({'coin': coin,
                            'status': 'RESEARCH_ONLY_POSITIVE' if accepted else 'INSUFFICIENT_EVIDENCE',
                            'folds': len(folds),
                            'reasons': [reason for _, reason in reasons]})

    complete = len(actual) == len(required) and set(actual) == set(required)
    ready_for_review = complete and all(x['status'] == 'RESEARCH_ONLY_POSITIVE' for x in assessments)
    return {
        'research_complete_for_review': ready_for_review,
        'approved_for_live_trading': False,
        'tested_symbols': len([a for a in assessments if a['status'] != 'NOT_EVALUATED']),
        'required_symbols': len(required),
        'coins': assessments,
        'notes': ['A positive holdout across folds is not proof of live trading edge.',
                  'Portfolio correlation, multiple comparisons, latency and real fills remain unverified.',
                  'No automatic trading configuration changes are permitted.'],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', default='research_data/walkforward_results.json')
    parser.add_argument('--output', default='research_data/evidence_assessment.json')
    args = parser.parse_args()
    source = Path(args.input)
    content = source.read_bytes()
    payload = json.loads(content)
    if not isinstance(payload, dict) or not isinstance(payload.get('results'), list):
        raise ValueError('Expected the JSON output of backtest.walkforward')
    result = assess(payload['results'])
    result['evaluated_at_utc'] = datetime.now(timezone.utc).isoformat()
    result['source_sha256'] = hashlib.sha256(content).hexdigest()
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2) + '\n')
    print(f'Assessed {result["tested_symbols"]}/{result["required_symbols"]} coins; '
          f'research_complete_for_review={result["research_complete_for_review"]}; '
          f'live_approval={result["approved_for_live_trading"]}')


if __name__ == '__main__':
    main()
