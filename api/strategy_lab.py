"""Private, research-only endpoints; reuses existing operator authentication boundary."""
from __future__ import annotations
import asyncio
from fastapi import APIRouter, HTTPException, Request, Query
from pydantic import BaseModel, Field
from config import COIN_CONFIG
from operator_auth import require_operator
from strategies.registry import STRATEGIES, STRATEGY_RELEASE
from research.lab import run_cached
from research.ledger import persist_experiment, list_experiments, list_shadow

router=APIRouter(tags=["strategy-lab"])


def _auth(request: Request) -> None:
    if not require_operator(request):
        raise HTTPException(401,"Unauthorized")


class ExperimentRequest(BaseModel):
    coin: str = Field(min_length=2,max_length=8)
    strategy: str = Field(min_length=3,max_length=50)
    min_volume_ratio: float = Field(default=1.2,ge=.5,le=4)


@router.get("/strategy-lab/registry")
def registry(request:Request):
    _auth(request)
    return {"version":STRATEGY_RELEASE,"strategies":[{"id":k,"label":v,"execution_enabled":False,"status":"research_only"} for k,v in STRATEGIES.items()],"coins":list(COIN_CONFIG),"execution_linked":False,"feed":"Binance cached closed 4h candles","notice":"No candidate strategies are automatically executable."}


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


@router.get("/market-intelligence/{coin}")
async def market_intelligence(request:Request, coin:str):
    _auth(request)
    if coin.upper() not in COIN_CONFIG:
        raise HTTPException(422,"Coin is outside configured universe")
    from intelligence.binance import overview
    return await overview(coin)
