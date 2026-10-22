"""3.4 structural risk, transparent decisions and retained audit tests."""
from datetime import datetime, timedelta, timezone
import numpy as np
import pandas as pd
import pytest
from strategies.registry import scan, features, _structure_levels, STRATEGIES


def market(candles=330):
    rng=np.random.default_rng(34)
    closes=100*np.exp(np.cumsum(rng.normal(.0001,.009,candles)))
    opens=np.r_[closes[0],closes[:-1]]
    high=np.maximum(opens,closes)*1.013
    low=np.minimum(opens,closes)*.987
    volume=rng.uniform(100,1000,candles)
    idx=pd.date_range('2025-01-01',periods=candles,freq='4h',tz='UTC')
    return pd.DataFrame({'open':opens,'high':high,'low':low,'close':closes,'volume':volume},index=idx)


def test_four_strategies_have_named_evidence_checks():
    a=scan(market())
    assert {x['strategy'] for x in a}==set(STRATEGIES)
    for item in a:
        assert item['checks']
        assert all(set(c)>={'name','actual','required','passed'} for c in item['checks'])
        assert all(type(c['passed']) is bool for c in item['checks'])
        assert 'undefined' not in str(item['checks']).lower()


def test_structure_stop_and_target_use_observed_history_not_fixed_reward():
    d=features(market())
    x=d.iloc[-1]
    stop,target,source=_structure_levels(d,'trend_continuation','LONG')
    assert stop<d.low.iloc[-21:-1].min()
    assert source in ('nearest_observed_resistance','no_observable_resistance')
    if np.isfinite(target):
        assert abs(target-x.close)/abs(x.close-stop) != pytest.approx(2.0,abs=1e-5)


def test_research_does_not_rewrite_history():
    d=market()
    a=scan(d.iloc[:-12])
    modified=d.copy()
    modified.iloc[-10:,modified.columns.get_loc('close')]*=1.2
    assert a==scan(modified.iloc[:-12])


def test_expire_only_unresolved_stale_signals_and_keep_records():
    from database import Base, engine, Signal, get_session
    from data.signal_lifecycle import expire_actionable_signals
    Base.metadata.create_all(engine)
    old=datetime.now(timezone.utc).replace(tzinfo=None)-timedelta(hours=25)
    current=datetime.now(timezone.utc).replace(tzinfo=None)
    with get_session() as db:
        stale=Signal(coin='TEST34',outcome='pending',timestamp=old,market='crypto')
        fresh=Signal(coin='TEST34',outcome='pending',timestamp=current,market='crypto')
        completed=Signal(coin='TEST34',outcome='win',timestamp=old,market='crypto')
        db.add_all([stale,fresh,completed]);db.flush();ids=[stale.id,fresh.id,completed.id]
    count=expire_actionable_signals(max_age_hours=12)
    assert count>=1
    with get_session() as db:
        rows=[db.get(Signal,i) for i in ids]
        assert [r.outcome for r in rows]==['expired','pending','win']
        for row in rows:db.delete(row)


def test_malformed_expiry_policy_is_rejected():
    from data.signal_lifecycle import expire_actionable_signals
    for bad in [-3,0,200]:
        with pytest.raises(ValueError):expire_actionable_signals(max_age_hours=bad)
