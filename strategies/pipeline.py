"""Unified production + research strategy evaluation.

No new order-placing implementation is introduced: selected proposals pass to
scanner.py, which uses its existing Binance executor / order journal. Strategy
rules are precisely the ones used by the shared replay engine.
"""
from __future__ import annotations

import math
import time
from engines.scoring.scorer import get_session
from strategies.registry import STRATEGIES, features, evaluate


def grade_score(value: float) -> str:
    # Explicit deterministic cross-strategy eligibility thresholds, not an
    # assertion that scores represent calibrated probability of success.
    return 'A+' if value >= 85 else 'A' if value >= 72 else 'B' if value >= 60 else 'F'


def arbitrate(events: list[dict], controls: dict[str, dict]) -> tuple[dict | None, str]:
    """Fail closed on opposite-side candidates; never stack a single symbol."""
    eligible = [e['candidate'] for e in events if e.get('candidate') and
                controls.get(e['strategy'],{}).get('execution_enabled',False) and
                grade_score(float(e['candidate']['score'])) in ('A+', 'A')]
    if not eligible:
        return None, 'no_executable_eligible_candidate'
    if len({c['direction'] for c in eligible}) > 1:
        return None, 'opposing_strategy_conflict'
    # Priority stable across restarts; score is heuristic, not success probability.
    priority = {name: idx for idx,name in enumerate(STRATEGIES)}
    eligible.sort(key=lambda c: (-float(c['score']), priority[c['strategy']]))
    return eligible[0], 'selected_one_position_per_coin'


def evaluate_all(frame, controls: dict[str,dict]) -> list[dict]:
    # Feature calculation happens once for all strategies; params are shared
    # with the research engine, no private duplicate trend implementation.
    enabled = {name for name in STRATEGIES if controls.get(name,{}).get('scan_enabled')}
    if not enabled:
        return []
    prepared = features(frame)
    return [evaluate(prepared, name) for name in STRATEGIES if name in enabled]


def as_trade(candidate: dict, *, coin: str, balance: float, started: float) -> dict:
    """Translate strategy proposal into the existing common risk/sizing contract."""
    from engines.sizing.adaptive import calculate
    from config import get_coin_config
    direction = candidate['direction']
    entry, sl, tp = (float(candidate[k]) for k in ('entry','stop','target'))
    if not all(math.isfinite(n) and n > 0 for n in (entry,sl,tp)):
        return {'signal':False, 'reason':'invalid_strategy_levels','coin':coin}
    risk_distance = abs(entry-sl)
    if direction == 'LONG' and not (sl < entry < tp) or direction == 'SHORT' and not (tp < entry < sl):
        return {'signal':False,'reason':'invalid_strategy_direction','coin':coin}
    rr = abs(tp-entry)/risk_distance
    # The shared existing system's configured minimum RR policy applies here.
    required = float(get_coin_config(coin).get('tp', 2.0))
    if rr + 1e-6 < .90*required:
        return {'signal':False,'reason':'coin_rr_gate','coin':coin}
    grade = grade_score(float(candidate['score']))
    if grade not in ('A+','A'):
        return {'signal':False,'reason':'below_execution_grade','coin':coin}
    risk_pct = 100 * risk_distance / entry
    sizing = calculate(balance=balance, sl_pct=risk_pct, sl_dist=risk_distance,
                       grade=grade, direction=direction,
                       regime_mult=.7 if candidate['regime'] in ('ranging','transition') else 1.,
                       session=get_session(), coin=coin)
    if sizing.skip:
        return {'signal':False,'reason':'sizing:'+sizing.reason,'coin':coin}
    trace = {'steps':[{'node':'strategy','passed':True,'strategy':candidate['strategy'],
                        'direction':direction,'reason':candidate['reason']},
                       {'node':'sizing','passed':True,'stake':sizing.stake,'leverage':sizing.leverage}],
             'strategy': candidate['strategy'], 'entry_features':{'score':candidate['score']},
             'direction':direction,'grade':grade,'score':candidate['score']}
    return {'signal':True,'coin':coin,'direction':direction,'grade':grade,
            'score':float(candidate['score']), 'strategy_id':candidate['strategy'],
            'entry':entry,'sl':sl,'tp1':tp,'tp2':None,'sl_pct':risk_pct,
            'sl_dist':risk_distance,'rr1':rr,'rr2':None,
            'risk_amt':sizing.risk_amt,'pos_size':sizing.position_size,
            'stake':sizing.stake,'leverage':sizing.leverage,'risk_pct':sizing.risk_pct,
            'regime':candidate['regime'],'session':get_session(),
            'adx':0.,'agent_ms':round((time.monotonic()-started)*1000,1),
            'agent_steps':len(trace['steps']), 'trace':trace}


async def run(coin, df_4h, df_1h, balance, controls=None):
    """Unified cycle. Return one selected executable proposal or a rejection."""
    from strategies.control import get_controls
    from research.ledger import record_shadow
    from asyncio import to_thread
    started = time.monotonic()
    controls = controls if controls is not None else await to_thread(get_controls)
    if df_4h is None or len(df_4h) < 220 or df_1h is None or len(df_1h) < 200:
        return {'signal':False,'coin':coin,'direction':'NEUTRAL','grade':'F',
                'score':0,'reason':'insufficient_closed_candle_data','trace':{'steps':[]}}
    try:
        events = await to_thread(evaluate_all,df_4h,controls)
        # This ledger now records actual main-pipeline evaluations, not a
        # separate shadow strategy path. Keep its old table for migration.
        if events:
            await to_thread(record_shadow,coin,events)
        chosen, reason = arbitrate(events,controls)
        trace = [{'node':'strategy_evaluation','strategy':e['strategy'],
                  'passed':e.get('candidate') is not None,
                  'reason':e.get('rejection') or 'candidate_detected'} for e in events]
        if chosen is None:
            return {'signal':False,'coin':coin,'direction':'NEUTRAL','grade':'F',
                    'score':0,'reason':reason,'regime':events[0]['regime'] if events else 'unknown',
                    'decisions':events,'agent_ms':round((time.monotonic()-started)*1000,1),
                    'agent_steps':len(trace),'trace':{'steps':trace}}
        trade = as_trade(chosen,coin=coin,balance=balance,started=started)
        trade['decisions'] = events
        trade['arbitration'] = reason
        if not trade['signal']:
            trade.update({'direction':'NEUTRAL','grade':'F','score':0,
                          'trace':{'steps':trace+[{'node':'risk','passed':False,
                                                    'reason':trade['reason']}]}})
        else:
            trade['trace']['steps'] = trace + trade['trace']['steps']
        return trade
    except Exception as exc:
        import logging
        logging.getLogger(__name__).exception('Strategy pipeline failure for %s',coin)
        return {'signal':False,'coin':coin,'direction':'NEUTRAL','grade':'F',
                'score':0,'reason':'pipeline_error:'+type(exc).__name__,
                'trace':{'steps':[{'node':'pipeline','passed':False}]}}
