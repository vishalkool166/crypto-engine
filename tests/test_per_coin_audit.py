"""No exchange calls or historical performance claims."""
from pathlib import Path
import pytest
from config import COIN_CONFIG
from backtest import per_coin_audit as audit


def test_all_18_symbols_have_current_and_control_arms():
    assert len(COIN_CONFIG) == 18
    for coin in COIN_CONFIG:
        options = audit.variants(coin)
        assert set(options) == {'configured', 'shared_reference', 'no_session_restriction',
                                'adx_20', 'tp_2R', 'no_loss_cooldown'}
        assert options['configured'] == {}


def test_temporary_override_restores_config_even_on_exception():
    original = COIN_CONFIG['ETH']
    with pytest.raises(RuntimeError):
        with audit.research_override('ETH', {'tp': 1.5, 'adx': 10}):
            assert COIN_CONFIG['ETH']['tp'] == 1.5
            raise RuntimeError('intentional failure')
    assert COIN_CONFIG['ETH'] is original
    assert original['tp'] == 2.0


def test_audit_reports_each_variant_without_mutating_live_config(monkeypatch, tmp_path):
    original = COIN_CONFIG['SUI']
    observed = []
    def fake_evaluate(coin, directory):
        assert coin == 'SUI'
        observed.append((COIN_CONFIG[coin]['tp'], COIN_CONFIG[coin]['session']))
        return {'total_trades': 4, 'total_signals': 5, 'win_rate': 50.,
                'profit_factor': 1.1, 'total_return': 1.0,
                'expectancy': 1.0, 'max_drawdown': 2.,
                'signals_per_30d': 3., 'fills_per_30d': 2.,
                'funding_modeled': False,
                'walk_forward': {'holdout': {'total_trades': 1, 'win_rate': 100.}}}
    monkeypatch.setattr(audit, 'evaluate', fake_evaluate)
    report = audit.audit_coin('SUI', tmp_path)
    assert len(report['variants']) == 6
    assert observed[0] == (2.5, 'ny')
    assert observed[1] == (2.0, 'all')
    assert COIN_CONFIG['SUI'] is original
    assert report['status'] == 'RESEARCH_ONLY_UNVERIFIED'
