"""No missing or ambiguous walk-forward result can be mistaken for a proven edge."""
from copy import deepcopy
import pytest
from backtest.evidence import assess


def _coin(symbol, count=2):
    return {'coin': symbol, 'validation': 'expanding_window_rolling_holdouts',
            'total_folds': count, 'folds': [
                {'holdout': {'total_trades': 23, 'total_signals': 40,
                             'expectancy': 2.5, 'total_pnl': 57.5,
                             'win_rate': 55.0, 'max_drawdown': 12.0,
                             'profit_factor': 1.5, 'funding_modeled': True,
                             'signals_per_30d': 7.2, 'fills_per_30d': 3.1}}
                for _ in range(count)]}


def test_missing_coin_blocks_research_completion():
    r = assess([_coin('ETH')], ('ETH', 'SOL'))
    assert r['research_complete_for_review'] is False
    assert r['approved_for_live_trading'] is False
    assert r['coins'][1]['status'] == 'NOT_EVALUATED'


def test_positive_two_coin_results_still_never_approve_live():
    r = assess([_coin('ETH'), _coin('SOL')], ('ETH', 'SOL'))
    assert r['research_complete_for_review'] is True
    assert r['approved_for_live_trading'] is False


@pytest.mark.parametrize('attribute,value,reason', [
    ('total_trades', 2, 'insufficient_holdout_trades'),
    ('funding_modeled', False, 'funding_unverified'),
    ('expectancy', -1, 'nonpositive_net_edge'),
    ('profit_factor', 0.9, 'nonpositive_net_edge'),
    ('expectancy', float('nan'), 'nonfinite_metrics'),
    ('signals_per_30d', -2, 'invalid_signal_frequency'),
    ('fills_per_30d', float('inf'), 'invalid_signal_frequency'),
    ('max_drawdown', 150, 'inconsistent_metrics'),
    ('total_pnl', -10, 'nonpositive_net_edge'),
    ('total_signals', 1, 'inconsistent_metrics'),
])
def test_bad_holdout_is_never_a_pass(attribute, value, reason):
    report = _coin('ETH')
    report['folds'][0]['holdout'][attribute] = value
    r = assess([report], ('ETH',))
    assert r['research_complete_for_review'] is False
    assert r['coins'][0]['reasons'][0] == reason


def test_duplicate_rows_fail_loudly():
    with pytest.raises(ValueError, match='Duplicate'):
        assess([_coin('ETH'), deepcopy(_coin('ETH'))], ('ETH',))


def test_inconsistent_fold_count_is_insufficient():
    report = _coin('ETH')
    report['total_folds'] = 100
    r = assess([report], ('ETH',))
    assert r['research_complete_for_review'] is False
