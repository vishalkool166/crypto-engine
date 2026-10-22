"""Regression tests for the read-only Signal Engine 3.0 additions."""
import asyncio
import inspect
import json
import math
import sys
import types

import numpy as np
import pandas as pd
import pytest

from strategies.registry import STRATEGIES, evaluate, features, scan
from research.lab import run_replay
from research.groq_provider import candidates
from intelligence.binance import safe_float


def candles(count=440):
    rng=np.random.default_rng(2026)
    closes=150*np.exp(np.cumsum(rng.normal(.0002,.008,count)))
    opens=np.r_[closes[0],closes[:-1]]
    highs=np.maximum(opens,closes)*1.01
    lows=np.minimum(opens,closes)*.99
    idx=pd.date_range('2025-01-01',periods=count,freq='4h',tz='UTC')
    return pd.DataFrame({'open':opens,'high':highs,'low':lows,'close':closes,'volume':rng.uniform(100,1000,count)},index=idx)


def test_every_strategy_is_deterministic_and_not_executable():
    frame=candles()
    a=scan(frame)
    assert len(a)==4
    assert a==scan(frame)
    assert {e['strategy'] for e in a}==set(STRATEGIES)
    assert all((not e['candidate']) or not e['candidate']['executable'] for e in a)


def test_future_prices_do_not_change_past_observation():
    frame=candles()
    past=scan(frame.iloc[:-10]); future=frame.copy()
    future.iloc[-9:,future.columns.get_loc('close')] *= 1.5
    assert past==scan(future.iloc[:-10])


def test_invalid_data_and_config_fail_closed():
    frame=candles()
    with pytest.raises(ValueError): scan(frame.iloc[:-1].iloc[::-1])
    with pytest.raises(ValueError): scan(frame,{'min_volume_ratio':0})
    with pytest.raises(ValueError): scan(frame,only='unknown')
    bad=frame.copy();bad.iloc[-1,bad.columns.get_loc('close')] = -1
    with pytest.raises(ValueError): scan(bad)


def test_replay_reproducible_with_fees_and_no_certification():
    frame=candles()
    a=run_replay(frame,'trend_continuation')
    b=run_replay(frame,'trend_continuation')
    assert a==b
    assert a['data_sha256']==b['data_sha256']
    assert a['simulated'] and not a['funding_modeled']
    assert a['status']=='RESEARCH_ONLY_UNCERTIFIED'
    assert a['holdout']['trades'] <= a['all_trades']
    assert all(t['fees'] >= 0 for t in a['trades'])
    assert all(t['entry_at']>t['signal_at'] for t in a['trades'])
    assert not any(t['segment']=='development' and t['exit_at'] >= a['holdout_from'] for t in a['trades'])


def test_replay_short_history_rejected():
    with pytest.raises(ValueError): run_replay(candles(225),'breakout_retest')


def test_groq_model_defaults_to_free_supported_production_model(monkeypatch):
    monkeypatch.delenv('GROQ_MODEL',raising=False)
    assert candidates()[0]=='openai/gpt-oss-20b'
    monkeypatch.setenv('GROQ_MODEL','llama-3.3-70b-versatile')
    assert candidates()[0]=='openai/gpt-oss-20b'


def test_binance_unavailable_fields_are_not_invented():
    assert safe_float({},'longShortRatio') is None
    assert safe_float({'longShortRatio':'NaN'},'longShortRatio') is None
    assert safe_float({'longShortRatio':'1.24'},'longShortRatio') == 1.24


def test_new_strategies_have_no_exchange_order_calls():
    import strategies.registry as registry
    import research.lab as lab
    for m in (registry,lab):
        source=inspect.getsource(m)
        assert 'create_order(' not in source
        assert 'place_order(' not in source
        assert 'get_balance(' not in source


def test_free_groq_provider_falls_back_from_missing_model(monkeypatch):
    from research.groq_provider import complete
    class Rejected(Exception): pass
    class Answer:
        choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="READY"))]
    attempted=[]
    class C:
        def __init__(self,*a,**k):
            self.chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=self.create))
        async def __aenter__(self): return self
        async def __aexit__(self,*args): return False
        async def create(self,**kwargs):
            attempted.append(kwargs['model'])
            if len(attempted)==1: raise Rejected('fake unsupported model')
            return Answer()
    fake=types.ModuleType('groq')
    fake.AsyncGroq=C
    fake.BadRequestError=fake.NotFoundError=fake.PermissionDeniedError=Rejected
    monkeypatch.setitem(sys.modules,'groq',fake)
    monkeypatch.setenv('GROQ_API_KEY','unused-test-value')
    monkeypatch.setenv('GROQ_MODEL','custom/unavailable')
    output=asyncio.run(complete([{'role':'user','content':'test'}]))
    assert attempted==['custom/unavailable','openai/gpt-oss-20b']
    assert output=={'answer':'READY','model':'openai/gpt-oss-20b'}


def test_binance_signed_equity_fails_on_missing_and_invalid_data():
    import ast
    import pathlib
    source=pathlib.Path('trade/exchange.py').read_text()
    node=next(n for n in ast.parse(source).body if isinstance(n,ast.AsyncFunctionDef) and n.name=='get_account_equity')
    code=compile(ast.Module(body=[node],type_ignores=[]),'<test>','exec')
    async def good(*args,**kwargs):return {'totalMarginBalance':'123.45'}
    async def bad(*args,**kwargs):return {'totalMarginBalance':'NaN'}
    async def missing(*args,**kwargs):return {'totalWalletBalance':'123.45'}
    namespace={'_get':good}
    exec(code,namespace)
    assert asyncio.run(namespace['get_account_equity']())==123.45
    namespace['_get']=bad
    with pytest.raises(ValueError): asyncio.run(namespace['get_account_equity']())
    namespace['_get']=missing
    with pytest.raises(ValueError): asyncio.run(namespace['get_account_equity']())
