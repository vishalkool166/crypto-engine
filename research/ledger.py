"""Shared decision-observation ledger and research replay experiments."""
from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Integer, String, Text, Boolean, Float
from database import Base, get_session
import json


class StrategyExperiment(Base):
    __tablename__ = "strategy_experiments_v3"
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    coin = Column(String(12), nullable=False)
    strategy = Column(String(50), nullable=False)
    parameters_json = Column(Text, nullable=False)
    results_json = Column(Text, nullable=False)
    data_sha256 = Column(String(64), nullable=False)
    status = Column(String(50), default="RESEARCH_ONLY_UNCERTIFIED", nullable=False)


class ShadowObservation(Base):
    __tablename__ = "strategy_shadow_observations_v3"
    id = Column(Integer, primary_key=True)
    observed_at = Column(DateTime, default=lambda:datetime.now(timezone.utc),nullable=False)
    coin = Column(String(12),nullable=False)
    strategy = Column(String(50),nullable=False)
    direction = Column(String(10))
    regime = Column(String(30))
    score = Column(Float)
    reason = Column(String(80))
    candle_at = Column(String(40))
    payload_json = Column(Text,nullable=False)
    __table_args__ = ()


def persist_experiment(coin: str, result: dict) -> int:
    with get_session() as db:
        item = StrategyExperiment(coin=coin, strategy=result["strategy"],parameters_json=json.dumps(result["parameters"],sort_keys=True), results_json=json.dumps(result,allow_nan=False), data_sha256=result["data_sha256"],status=result["status"])
        db.add(item)
        db.flush()
        return item.id


def list_experiments(limit:int=30) -> list[dict]:
    with get_session() as db:
        rows = db.query(StrategyExperiment).order_by(StrategyExperiment.id.desc()).limit(min(max(limit,1),100)).all()
        return [{"id":r.id,"created_at":r.created_at.isoformat(),"coin":r.coin,"strategy":r.strategy,"data_sha256":r.data_sha256,"status":r.status, "summary":{k:json.loads(r.results_json).get(k) for k in ("development","holdout","bars","holdout_from","funding_modeled")}} for r in rows]


def list_shadow(limit:int=60) -> list[dict]:
    with get_session() as db:
        rows=db.query(ShadowObservation).order_by(ShadowObservation.id.desc()).limit(min(max(limit,1),150)).all()
        result = []
        for r in rows:
            payload = json.loads(r.payload_json or '{}')
            candidate = payload.get('candidate') or {}
            result.append({'id':r.id,'observed_at':r.observed_at.isoformat(),
                           'coin':r.coin,'strategy':r.strategy,
                           'direction':r.direction,'score':r.score,
                           'reason':r.reason,'regime':r.regime,
                           'candle_at':r.candle_at,
                           'entry':candidate.get('entry'),
                           'stop':candidate.get('stop'),
                           'target':candidate.get('target'),
                           'target_source':candidate.get('target_source'),
                           'available_rr':candidate.get('available_rr'),
                           'checks':payload.get('checks',[])})
        return result


def record_shadow(coin:str, events: list[dict]) -> None:
    """Persist main-scanner strategy decisions; avoid duplicates per candle."""
    with get_session() as db:
        for event in events:
            cand=event.get("candidate") or {}
            if db.query(ShadowObservation.id).filter_by(coin=coin,strategy=event["strategy"],candle_at=event["observed_at"]).first():
                continue
            db.add(ShadowObservation(coin=coin,strategy=event["strategy"],direction=cand.get("direction"),score=cand.get("score"),regime=event["regime"],reason=event.get("rejection") or "candidate_detected",candle_at=event["observed_at"],payload_json=json.dumps(event,default=str)))
        db.flush()
        # Keep bounded without allowing a scan to grow disk forever.
        ids = [a for (a,) in db.query(ShadowObservation.id).order_by(ShadowObservation.id.desc()).offset(3000).all()]
        if ids:
            db.query(ShadowObservation).filter(ShadowObservation.id.in_(ids)).delete(synchronize_session=False)
