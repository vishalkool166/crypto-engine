"""Private, research-only endpoints; reuses existing operator authentication boundary."""
from __future__ import annotations
import asyncio
from fastapi import APIRouter, HTTPException, Request, Query
from pydantic import BaseModel, Field, StrictBool
from config import COIN_CONFIG
from operator_auth import require_operator
from strategies.registry import STRATEGIES, STRATEGY_RELEASE
from research.lab import run_cached
from research.ledger import persist_experiment, list_experiments, list_shadow
from strategies.control import get_controls, update_control

router=APIRouter(tags=["strategy-lab"])


def _auth(request: Request) -> None:
    if not require_operator(request):
        raise HTTPException(401,"Unauthorized")


class ControlRequest(BaseModel):
    scan_enabled: StrictBool
    execution_enabled: StrictBool


class ExperimentRequest(BaseModel):
    coin: str = Field(min_length=2,max_length=8)
    strategy: str = Field(min_length=3,max_length=50)
    min_volume_ratio: float = Field(default=1.2,ge=.5,le=4)


@router.get("/strategy-lab/registry")
def registry(request: Request):
    _auth(request)
    controls = get_controls()
    return {"version":STRATEGY_RELEASE,
            "strategies":[{"id":k,"label":v,**controls.get(k,{})} for k,v in STRATEGIES.items()],
            "coins":list(COIN_CONFIG),"execution_linked":True,
            "feed":"Binance verified closed 4h candles",
            "notice":"All four strategies share the active scanner and central Binance risk/execution path. Account mode controls paper vs live."}


@router.get("/strategy-lab/controls")
def controls(request: Request):
    _auth(request)
    return {"strategies":get_controls()}


@router.put("/strategy-lab/controls/{strategy}")
def set_controls(request: Request, strategy: str, payload: ControlRequest):
    _auth(request)
    try:
        result = update_control(strategy,scan_enabled=payload.scan_enabled,
                                execution_enabled=payload.execution_enabled)
        return {"strategy":strategy,**result}
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from None


@router.get("/strategy-lab/candles/{coin}")
def candles(request: Request, coin: str):
    _auth(request)
    if coin.upper() not in COIN_CONFIG:
        raise HTTPException(422,"Unknown configured Binance market")
    from data.store import load_candles
    candles = load_candles(coin.upper(),"4h",limit=150)
    if candles is None or candles.empty:
        return {"coin":coin.upper(),"candles":[],"timeframe":"4h", "source":"local closed Binance candles"}
    rows = []
    for timestamp, row in candles.tail(120).iterrows():
        rows.append({"time":str(timestamp),**{k:float(row[k]) for k in ("open","high","low","close","volume")}})
    return {"coin":coin.upper(),"candles":rows,"timeframe":"4h","source":"local closed Binance candles"}


@router.get("/strategy-lab/performance")
def strategy_performance(request: Request):
    """Observed CLOSED Binance trades grouped by strategy and execution mode."""
    _auth(request)
    from database import Trade, get_session
    from sqlalchemy import func
    with get_session() as db:
        grouped = (db.query(Trade.strategy_id, Trade.execution_mode,
                    func.count(Trade.id),func.sum(Trade.net_pnl),
                    func.sum(Trade.pnl))
                   .filter(Trade.market == 'crypto',
                           Trade.strategy_id.in_(list(STRATEGIES)),
                           Trade.state == 'closed')
                   .group_by(Trade.strategy_id, Trade.execution_mode).all())
    return {'items':[{'strategy':strategy,'mode':mode,'closed_trades':n,
                      'net_pnl_usdt':round(float(net if net is not None else gross or 0),4)}
                     for strategy,mode,n,net,gross in grouped],
            'note':'Stored closed trades only, separated by execution mode. No simulated results mixed in.'}


@router.get("/strategy-lab/experiments")
def experiments(request:Request,limit:int=Query(30,ge=1,le=100)):
    _auth(request)
    return {"items":list_experiments(limit)}


@router.get("/strategy-lab/shadow")
def shadow(request:Request,limit:int=Query(60,ge=1,le=150)):
    _auth(request)
    return {"items":list_shadow(limit)}


@router.post("/strategy-lab/run")
async def run(request:Request,payload:ExperimentRequest):
    _auth(request)
    coin=payload.coin.upper()
    if coin not in COIN_CONFIG or payload.strategy not in STRATEGIES:
        raise HTTPException(422,"Unknown configured market or strategy")
    try:
        result=await asyncio.to_thread(run_cached,coin,payload.strategy,{"min_volume_ratio":payload.min_volume_ratio})
        eid=await asyncio.to_thread(persist_experiment,coin,result)
        return {"experiment_id":eid,"coin":coin,**result}
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from None


@router.post("/strategy-lab/compare")
async def compare(request: Request, payload: ExperimentRequest):
    """Run all four same-data experiments; NOT an additive portfolio backtest."""
    _auth(request)
    coin=payload.coin.upper()
    if coin not in COIN_CONFIG:
        raise HTTPException(422,"Unknown configured Binance market")
    params={"min_volume_ratio":payload.min_volume_ratio}
    comparison=[]
    for strategy in STRATEGIES:
        try:
            result=await asyncio.to_thread(run_cached,coin,strategy,params)
            experiment_id=await asyncio.to_thread(persist_experiment,coin,result)
            comparison.append({"strategy":strategy,"experiment_id":experiment_id,
                "status":result["status"],"development":result["development"],
                "holdout":result["holdout"],"data_sha256":result["data_sha256"]})
        except ValueError as exc:
            raise HTTPException(422,str(exc)) from None
    return {"coin":coin,"items":comparison,
            "additive_portfolio_metrics":False,
            "notice":"Strategies were replayed separately using identical candles. Their P&L cannot be summed to represent a combined account."}


@router.get("/market-intelligence/{coin}")
async def market_intelligence(request:Request, coin:str):
    _auth(request)
    if coin.upper() not in COIN_CONFIG:
        raise HTTPException(422,"Coin is outside configured universe")
    from intelligence.binance import overview
    return await overview(coin)
