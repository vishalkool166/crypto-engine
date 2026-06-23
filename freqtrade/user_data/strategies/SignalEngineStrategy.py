import json
import logging
from datetime import datetime, timezone
from typing import Optional
from freqtrade.strategy import IStrategy
from freqtrade.persistence import Trade
from pandas import DataFrame

logger = logging.getLogger(__name__)

_redis_client = None


def _get_redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        import redis
        import os
        url = os.getenv("REDIS_URL", "redis://localhost:6379")
        client = redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=3
        )
        client.ping()
        _redis_client = client
        return _redis_client
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        return None


def _push_candles_to_redis(coin: str, tf: str, df: DataFrame):
    try:
        r = _get_redis()
        if not r or df is None or df.empty:
            return
        key = f"candles:{coin}USDT:{tf}"
        r.setex(key, 900, df.to_json())
    except Exception as e:
        logger.error(f"Redis candle push failed {coin} {tf}: {e}")


def _push_ticker_to_redis(coin: str, ticker: dict):
    try:
        r = _get_redis()
        if not r or not ticker:
            return
        key     = f"ticker:{coin}USDT"
        payload = json.dumps({
            "last":       ticker.get("last", 0),
            "percentage": ticker.get("percentage", 0)
        })
        r.setex(key, 60, payload)
    except Exception as e:
        logger.error(f"Redis ticker push failed {coin}: {e}")


def _push_funding_to_redis(coin: str, rate: float):
    try:
        r = _get_redis()
        if not r:
            return
        r.setex(f"funding:{coin}USDT", 300, str(rate))
    except Exception as e:
        logger.error(f"Redis funding push failed {coin}: {e}")


def _push_oi_to_redis(coin: str, oi: float):
    try:
        r = _get_redis()
        if not r:
            return
        r.setex(f"oi:{coin}USDT", 300, str(oi))
    except Exception as e:
        logger.error(f"Redis OI push failed {coin}: {e}")


def _push_oi_change_to_redis(coin: str, change: float):
    try:
        r = _get_redis()
        if not r:
            return
        r.setex(f"oi_change:{coin}USDT", 300, str(change))
    except Exception as e:
        logger.error(f"Redis OI change push failed {coin}: {e}")


def _push_ls_ratio_to_redis(coin: str, long_pct: float, short_pct: float):
    try:
        r = _get_redis()
        if not r:
            return
        payload = json.dumps({"long": long_pct, "short": short_pct})
        r.setex(f"ls_ratio:{coin}USDT", 300, payload)
    except Exception as e:
        logger.error(f"Redis LS ratio push failed {coin}: {e}")


class SignalEngineStrategy(IStrategy):

    INTERFACE_VERSION = 3

    stoploss   = -0.99
    timeframe  = "4h"
    can_short  = True

    minimal_roi = {"0": 100}

    process_only_new_candles = False
    use_exit_signal          = False
    exit_profit_only         = False

    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        inf   = []
        for pair in pairs:
            for tf in ["1w", "1d", "4h", "1h", "15m"]:
                inf.append((pair, tf))
        return inf

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: Optional[str],
                 side: str, **kwargs) -> float:
        import os
        leverage = int(os.getenv("LEVERAGE", 10))
        return min(float(leverage), max_leverage)

    def bot_loop_start(self, **kwargs):
        pairs   = self.dp.current_whitelist()
        dry_run = self.config.get("dry_run", True)

        for pair in pairs:
            try:
                coin = pair.replace("/USDT", "").replace(":USDT", "")

                for tf in ["1w", "1d", "4h", "1h", "15m"]:
                    try:
                        df = self.dp.get_pair_dataframe(pair, tf)
                        if df is not None and not df.empty:
                            _push_candles_to_redis(coin, tf, df)
                    except Exception as e:
                        logger.warning(f"OHLCV push failed {coin} {tf}: {e}")

                try:
                    ticker = self.dp.ticker(pair)
                    if ticker:
                        _push_ticker_to_redis(coin, ticker)
                except Exception as e:
                    logger.warning(f"Ticker push failed {coin}: {e}")

                try:
                    result = self.dp._exchange._api.fetch_funding_rate(pair)
                    if result:
                        _push_funding_to_redis(coin, float(result.get("fundingRate", 0)))
                except Exception as e:
                    logger.warning(f"Funding push failed {coin}: {e}")

                try:
                    result = self.dp._exchange._api.fetch_open_interest(pair)
                    if result:
                        _push_oi_to_redis(coin, float(result.get("openInterestAmount", 0)))
                except Exception as e:
                    logger.warning(f"OI push failed {coin}: {e}")

                try:
                    hist = self.dp._exchange._api.fetch_open_interest_history(
                        pair, "1d", limit=2
                    )
                    if hist and len(hist) >= 2:
                        cur    = float(hist[-1].get("openInterestAmount", 0))
                        prev   = float(hist[-2].get("openInterestAmount", 0))
                        change = ((cur - prev) / prev * 100) if prev > 0 else 0.0
                        _push_oi_change_to_redis(coin, change)
                except Exception as e:
                    logger.warning(f"OI change push failed {coin}: {e}")

                if not dry_run:
                    try:
                        response = self.dp._exchange._api.request(
                            "GET",
                            "/futures/data/globalLongShortAccountRatio",
                            params={
                                "symbol": f"{coin}USDT",
                                "period": "1h",
                                "limit":  1
                            }
                        )
                        if response and len(response) > 0:
                            long_pct  = float(response[0].get("longAccount",  0)) * 100
                            short_pct = float(response[0].get("shortAccount", 0)) * 100
                            _push_ls_ratio_to_redis(coin, long_pct, short_pct)
                    except Exception as e:
                        logger.warning(f"LS ratio push failed {coin}: {e}")

            except Exception as e:
                logger.error(f"bot_loop_start error for {pair}: {e}")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["enter_long"]  = 0
        dataframe["enter_short"] = 0
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"]  = 0
        dataframe["exit_short"] = 0
        return dataframe