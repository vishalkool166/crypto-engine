"""Unified pipeline regression: arbitration, eligibility and database controls."""
import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from strategies.registry import STRATEGIES
from strategies.pipeline import arbitrate, as_trade, grade_score, evaluate_all, run


def controls(active=True):
    return {s:{'scan_enabled':active,'execution_enabled':active} for s in STRATEGIES}


def event(s, direction='LONG', score=80):
    return {'strategy':s,'candidate':{'strategy':s,'direction':direction,'score':score,
            'entry':100.,'stop':97.,'target':106.,'regime':'trending',
            'reason':'confirmed'},'rejection':None,'regime':'trending','observed_at':'2026-01-01'}


def test_one_market_one_candidate_and_stable_priority():
    a,b=list(STRATEGIES)[:2]
    winner,reason=arbitrate([event(b),event(a)],controls())
    assert winner['strategy']==a and reason=='selected_one_position_per_coin'


def test_opposite_signals_never_stack_or_net():
    a,b=list(STRATEGIES)[:2]
    winner,reason=arbitrate([event(a,'LONG'),event(b,'SHORT')],controls())
    assert winner is None and reason=='opposing_strategy_conflict'


def test_strategy_execution_flag_is_enforced():
    a,b=list(STRATEGIES)[:2]
    modes=controls()
    modes[a]['execution_enabled']=False
    winner,_=arbitrate([event(a,score=90),event(b,score=78)],modes)
    assert winner['strategy']==b
    winner,_=arbitrate([event(a,score=90)],modes)
    assert winner is None


def test_no_unqualified_candidates_can_execute():
    assert grade_score(65)=='B'
    assert arbitrate([event('trend_continuation',score=65)],controls())[0] is None
    assert arbitrate([{'strategy':'range_reversion','candidate':None}],controls())[0] is None


def test_as_trade_passes_shared_size_contract_not_custom_orders(monkeypatch):
    import engines.sizing.adaptive as sizing
    import config
    calls=[]
    def calculate(**kw):
        calls.append(kw)
        return SimpleNamespace(skip=False,stake=24.0,leverage=2,risk_amt=1.2,
                               position_size=48.0,risk_pct=.5)
    monkeypatch.setattr(sizing,'calculate',calculate)
    monkeypatch.setattr(config,'get_coin_config',lambda c:{'tp':2.0})
    result=as_trade(event('breakout_retest')['candidate'],coin='ETH',balance=300.,started=0.)
    assert result['signal'] and result['strategy_id']=='breakout_retest'
    assert result['sl_pct']==3. and calls[0]['direction']=='LONG'
    assert result['tp1']==106. and result['stake']==24.


def test_bad_trade_levels_never_reach_sizing():
    proposal=event('momentum_reversal')['candidate']
    proposal['stop']=120.
    result=as_trade(proposal,coin='BTC',balance=100,started=0.)
    assert not result['signal'] and result['reason']=='invalid_strategy_direction'


def test_pipeline_routes_all_strategies_and_persists_decisions(monkeypatch):
    import strategies.pipeline as p
    called=[]
    def scan_only(frame,settings):
        called.append('scan')
        return [event('breakout_retest',score=88)]
    async def no_db(*args):called.append('ledger')
    monkeypatch.setattr(p,'evaluate_all',scan_only)
    monkeypatch.setattr(p,'as_trade',lambda *a,**kw:{'signal':True,'strategy_id':'breakout_retest','trace':{'steps':[]}})
    import research.ledger as ledger
    monkeypatch.setattr(ledger,'record_shadow',lambda *a:called.append('ledger'))
    r=asyncio.run(run('BTC',[1]*220,[1]*200,100.,controls()))
    assert r['signal'] and r['strategy_id']=='breakout_retest'
    assert called==['scan','ledger']


def test_disabled_scanners_do_not_produce_trade():
    # No need to hit exchange, DB, or sizing with disabled scanner.
    assert evaluate_all(None,controls(False))==[]


def test_live_orders_remain_under_existing_exchange_guard():
    source=Path('alerts/scanner.py').read_text()
    assert 'from strategies.pipeline import run as agent_run' in source
    assert 'from trade.executor import open_position' in source
    assert 'strategy_id = signal.get("strategy_id")' in source
    assert 'ensure_live_opt_in(cfg.TRADING_MODE)' in Path('trade/executor.py').read_text()
    assert 'operator_execution_mode' in Path('trade/mode.py').read_text()


def test_no_new_credential_or_env_required():
    assert 'os.getenv' not in Path('strategies/control.py').read_text()
    assert 'os.getenv' not in Path('strategies/pipeline.py').read_text()
