"""Research-only per-coin config ablation; never changes persistent/live settings.

Runs configured settings versus a shared reference and one-knob ablations.
The 70/30 chronological split in backtest.engine is DESCRIPTIVE, not a true
walk-forward validation. This module must not label any config profitable or
promote an experimental configuration to production automatically.

Requires previously downloaded 1h/4h/funding CSVs and installed indicator
library `ta`. Usage:
    python -m backtest.per_coin_audit --data-dir research_data
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
from pathlib import Path

from config import COIN_CONFIG
from backtest.research import evaluate

# Predeclared reference; not optimized to data or to any individual coin.
SHARED_REFERENCE = {
    "adx": 20,
    "tp": 2.0,
    "session": "all",
    "skip_after_loss": False,
}


def variants(coin: str) -> dict[str, dict]:
    """Explicit counterfactuals, leaving risk/coin SL semantics unchanged."""
    live = COIN_CONFIG[coin]
    return {
        "configured": {},
        "shared_reference": SHARED_REFERENCE.copy(),
        "no_session_restriction": {"session": "all"},
        "adx_20": {"adx": 20},
        "tp_2R": {"tp": 2.0},
        "no_loss_cooldown": {"skip_after_loss": False},
    }


@contextmanager
def research_override(coin: str, overrides: dict):
    """Isolated single-process CLI override. Do not call in server workers.

    Uses a temporary dict replacement because trend/risk/sizing read the
    central COIN_CONFIG. Always restores original object, including on error.
    """
    original = COIN_CONFIG[coin]
    COIN_CONFIG[coin] = {**original, **overrides}
    try:
        yield COIN_CONFIG[coin]
    finally:
        COIN_CONFIG[coin] = original


def _compact(report: dict) -> dict:
    if 'error' in report:
        return {"error": report['error'], "rejections": report.get('rejections', {})}
    keys = ('total_trades', 'total_signals', 'win_rate', 'profit_factor',
            'total_return', 'expectancy', 'max_drawdown', 'signals_per_30d',
            'fills_per_30d', 'funding_modeled', 'period_start', 'period_end')
    values = {k: report.get(k) for k in keys}
    wf = report.get('walk_forward', {})
    values['descriptive_holdout'] = {
        k: wf.get('holdout', {}).get(k)
        for k in ('total_trades', 'win_rate', 'profit_factor', 'total_return',
                  'expectancy', 'max_drawdown')
    }
    return values


def audit_coin(coin: str, data_dir: Path) -> dict:
    if coin not in COIN_CONFIG:
        raise ValueError(f'Coin not configured: {coin}')
    output = {'coin': coin, 'live_config': COIN_CONFIG[coin].copy(), 'variants': {},
              'status': 'RESEARCH_ONLY_UNVERIFIED',
              'notes': [
                  'Do not select variants based on the descriptive 70/30 holdout.',
                  'Per-coin sl is currently unused by live risk calculation.',
                  'Per-coin numeric tier has no identified live risk/entry effect.',
                  'This is not live broker parity or verified profitability.',
              ]}
    for name, override in variants(coin).items():
        with research_override(coin, override):
            output['variants'][name] = _compact(evaluate(coin, data_dir))
    return output


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--coins', default=','.join(COIN_CONFIG))
    ap.add_argument('--data-dir', default='research_data')
    ap.add_argument('--output', default='research_data/per_coin_audit.json')
    args = ap.parse_args()
    data_dir = Path(args.data_dir)
    result = []
    for coin in [x.strip().upper() for x in args.coins.split(',') if x.strip()]:
        try:
            report = audit_coin(coin, data_dir)
        except Exception as error:
            report = {'coin': coin, 'error': str(error), 'status': 'NOT_EVALUATED'}
        result.append(report)
        print(coin, report['status'])
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'disclaimer': 'Exploratory simulated fills; not verified profitability',
                                'results': result}, indent=2, default=str) + '\n')
    print('Wrote', path)


if __name__ == '__main__':
    main()
