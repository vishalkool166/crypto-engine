import json
import time
import logging
import requests
from datetime import datetime, timezone
from typing import Optional
from freqtrade.strategy import IStrategy
from freqtrade.persistence import Trade
from pandas import DataFrame
import pandas as pd

logger = logging.getLogger(__name__)

REDIS_URL = None
_redis_client = None


def _get_redis():
    global _redis_client, REDIS_URL
    if _redis_client is not None:
        return _redis_client
    try:
        import redis
        import os
        REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
        client = redis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=3
        )
        client.ping()
        _redis_client = client
        logger.info(f"Freqtrade Redis connected: {REDIS_URL}")
        return _redis_client
    except Exception as e:
        logger.error(f"Freqtrade Redis connection failed: {e}")
        return None


def _get_signal(coin: str) -> dict | None:
    try:
        r = _get_redis()
        if not r:
            return None
        key  = f"signal:{coin}USDT"
        data = r.get(key)
        if not data:
            return None
        sig = json.loads(data)
        if time.time() > sig.get("valid_until", 0):
            logger.info(f"Signal expired for {coin}")
            return None
        return sig
    except Exception as e:
        logger.error(f"Redis signal read failed {coin}: {e}")
        return None


def _push_candles_to_redis(coin: str, tf: str, df: DataFrame):
    try:
        r = _get_redis()
        if not r or df is None or df.empty:
            return
        key = f"candles:{coin}USDT:{tf}"
        r.setex(key, 900, df.to_json())
        logger.debug(f"Candles pushed to Redis: {key} ({len(df)} rows)")
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
        logger.debug(f"Ticker pushed to Redis: {key}")
    except Exception as e:
        logger.error(f"Redis ticker push failed {coin}: {e}")


def _push_funding_to_redis(coin: str, rate: float):
    try:
        r = _get_redis()
        if not r:
            return
        key = f"funding:{coin}USDT"
        r.setex(key, 300, str(rate))
        logger.debug(f"Funding pushed to Redis: {key} = {rate}")
    except Exception as e:
        logger.error(f"Redis funding push failed {coin}: {e}")


def _push_oi_to_redis(coin: str, oi: float):
    try:
        r = _get_redis()
        if not r:
            return
        key = f"oi:{coin}USDT"
        r.setex(key, 300, str(oi))
        logger.debug(f"OI pushed to Redis: {key} = {oi}")
    except Exception as e:
        logger.error(f"Redis OI push failed {coin}: {e}")


def _push_oi_change_to_redis(coin: str, change: float):
    try:
        r = _get_redis()
        if not r:
            return
        key = f"oi_change:{coin}USDT"
        r.setex(key, 300, str(change))
        logger.debug(f"OI change pushed to Redis: {key} = {change}")
    except Exception as e:
        logger.error(f"Redis OI change push failed {coin}: {e}")


def _push_ls_ratio_to_redis(coin: str, long_pct: float, short_pct: float):
    try:
        r = _get_redis()
        if not r:
            return
        key     = f"ls_ratio:{coin}USDT"
        payload = json.dumps({"long": long_pct, "short": short_pct})
        r.setex(key, 300, payload)
        logger.debug(f"LS ratio pushed to Redis: {key}")
    except Exception as e:
        logger.error(f"Redis LS ratio push failed {coin}: {e}")


class SignalEngineStrategy(IStrategy):

    INTERFACE_VERSION = 3

    stoploss   = -0.99
    timeframe  = "4h"
    can_short  = True

    minimal_roi = {"0": 100}

    process_only_new_candles = True
    use_exit_signal          = False
    exit_profit_only         = False

    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        inf   = []
        for pair in pairs:
            for tf in ["1w", "1d", "4h", "1h", "15m"]:
                inf.append((pair, tf))
        return inf

    def bot_loop_start(self, **kwargs):
        pairs = self.dp.current_whitelist()

        for pair in pairs:
            try:
                coin = pair.replace("/USDT", "").replace(":USDT", "")

                # Push OHLCV for all timeframes
                for tf in ["1w", "1d", "4h", "1h", "15m"]:
                    try:
                        df = self.dp.get_pair_dataframe(pair, tf)
                        if df is not None and not df.empty:
                            _push_candles_to_redis(coin, tf, df)
                    except Exception as e:
                        logger.warning(f"OHLCV push failed {coin} {tf}: {e}")

                # Push ticker
                try:
                    ticker = self.dp.ticker(pair)
                    if ticker:
                        _push_ticker_to_redis(coin, ticker)
                except Exception as e:
                    logger.warning(f"Ticker push failed {coin}: {e}")

                # Push funding rate
                try:
                    result = self.dp._exchange._api.fetch_funding_rate(pair)
                    if result:
                        rate = float(result.get("fundingRate", 0))
                        _push_funding_to_redis(coin, rate)
                except Exception as e:
                    logger.warning(f"Funding push failed {coin}: {e}")

                # Push open interest
                try:
                    result = self.dp._exchange._api.fetch_open_interest(pair)
                    if result:
                        oi = float(result.get("openInterestAmount", 0))
                        _push_oi_to_redis(coin, oi)
                except Exception as e:
                    logger.warning(f"OI push failed {coin}: {e}")

                # Push OI change
                try:
                    hist = self.dp._exchange._api.fetch_open_interest_history(
                        pair, "1d", limit=2
                    )
                    if hist and len(hist) >= 2:
                        cur  = float(hist[-1].get("openInterestAmount", 0))
                        prev = float(hist[-2].get("openInterestAmount", 0))
                        change = ((cur - prev) / prev * 100) if prev > 0 else 0.0
                        _push_oi_change_to_redis(coin, change)
                except Exception as e:
                    logger.warning(f"OI change push failed {coin}: {e}")

                # Push long/short ratio
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
        pair = metadata.get("pair", "")
        coin = pair.replace("/USDT", "").replace(":USDT", "")

        dataframe["enter_long"]  = 0
        dataframe["enter_short"] = 0

        try:
            signal = _get_signal(coin)
            if not signal:
                return dataframe

            if signal.get("grade") not in ["A+", "A"]:
                return dataframe

            side = signal.get("side", "")

            if side == "long":
                dataframe.loc[dataframe.index[-1], "enter_long"] = 1
                logger.info(
                    f"Entry signal LONG: {coin} "
                    f"Grade:{signal.get('grade')} "
                    f"Score:{signal.get('score')} "
                    f"Entry:{signal.get('entry')}"
                )
            elif side == "short":
                dataframe.loc[dataframe.index[-1], "enter_short"] = 1
                logger.info(
                    f"Entry signal SHORT: {coin} "
                    f"Grade:{signal.get('grade')} "
                    f"Score:{signal.get('score')} "
                    f"Entry:{signal.get('entry')}"
                )

        except Exception as e:
            logger.error(f"populate_entry_trend error {coin}: {e}")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"]  = 0
        dataframe["exit_short"] = 0
        return dataframe

    def custom_stoploss(
        self,
        pair:         str,
        trade:        Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs
    ) -> float:
        coin = pair.replace("/USDT", "").replace(":USDT", "")

        try:
            signal = _get_signal(coin)
            if not signal:
                return self.stoploss

            stoploss_price = float(signal.get("stoploss", 0))
            if not stoploss_price or not trade.open_rate:
                return self.stoploss

            if trade.is_short:
                sl_pct = (stoploss_price - trade.open_rate) / trade.open_rate
            else:
                sl_pct = (stoploss_price - trade.open_rate) / trade.open_rate

            sl_pct = max(-0.99, min(-0.001, sl_pct))
            return sl_pct

        except Exception as e:
            logger.error(f"custom_stoploss error {coin}: {e}")
            return self.stoploss

    def custom_exit(
        self,
        pair:           str,
        trade:          Trade,
        current_time:   datetime,
        current_rate:   float,
        current_profit: float,
        **kwargs
    ) -> Optional[str]:
        coin = pair.replace("/USDT", "").replace(":USDT", "")

        try:
            signal = _get_signal(coin)
            if not signal:
                return None

            tp1 = float(signal.get("tp1", 0))
            if not tp1:
                return None

            if not trade.is_short and current_rate >= tp1:
                logger.info(f"TP1 hit LONG: {coin} current:{current_rate} tp1:{tp1}")
                return "tp1_hit"

            if trade.is_short and current_rate <= tp1:
                logger.info(f"TP1 hit SHORT: {coin} current:{current_rate} tp1:{tp1}")
                return "tp1_hit"

        except Exception as e:
            logger.error(f"custom_exit error {coin}: {e}")

        return None

    def confirm_trade_entry(
        self,
        pair:             str,
        order_type:       str,
        amount:           float,
        rate:             float,
        time_in_force:    str,
        current_time:     datetime,
        entry_tag:        Optional[str],
        side:             str,
        **kwargs
    ) -> bool:
        coin = pair.replace("/USDT", "").replace(":USDT", "")

        try:
            signal = _get_signal(coin)
            if not signal:
                logger.warning(f"confirm_trade_entry: no signal for {coin} — rejecting")
                return False

            if time.time() > signal.get("valid_until", 0):
                logger.warning(f"confirm_trade_entry: signal expired for {coin} — rejecting")
                return False

            entry_price = float(signal.get("entry", 0))
            if entry_price and rate:
                deviation = abs(rate - entry_price) / entry_price
                if deviation > 0.005:
                    logger.warning(
                        f"confirm_trade_entry: entry too stale for {coin} "
                        f"— deviation {deviation*100:.2f}% > 0.5% — rejecting"
                    )
                    return False

            logger.info(
                f"confirm_trade_entry: approved {coin} {side} "
                f"rate:{rate} entry:{entry_price}"
            )
            return True

        except Exception as e:
            logger.error(f"confirm_trade_entry error {coin}: {e}")
            return False