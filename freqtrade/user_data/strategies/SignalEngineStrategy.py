import json
import logging
import requests
from datetime import datetime, timezone
from typing import Optional
from freqtrade.strategy import IStrategy
from freqtrade.persistence import Trade
from pandas import DataFrame

logger = logging.getLogger(__name__)

_redis_client = None
_signal_cache = {}


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


def _get_backtest_signal(coin: str, date_str: str) -> dict | None:
    cache_key = f"{coin}_{date_str}"
    if cache_key in _signal_cache:
        return _signal_cache[cache_key]

    try:
        r = _get_redis()
        if r:
            redis_key = f"backtest_signal:{coin}:{date_str}"
            data = r.get(redis_key)
            if data:
                result = json.loads(data)
                _signal_cache[cache_key] = result
                return result

        response = requests.get(
            f"http://signal-engine:8000/api/backtest-signal/{coin}",
            params={"date": date_str},
            timeout=30
        )

        if response.status_code == 200:
            result = response.json()
            _signal_cache[cache_key] = result

            if r:
                redis_key = f"backtest_signal:{coin}:{date_str}"
                r.setex(redis_key, 86400, json.dumps(result))

            return result

    except Exception as e:
        logger.error(f"Backtest signal fetch failed {coin} {date_str}: {e}")

    return None


def _get_live_signal(coin: str) -> dict | None:
    try:
        r = _get_redis()
        if not r:
            return None
        key  = f"signal:{coin}USDT"
        data = r.get(key)
        if not data:
            return None
        import time
        sig = json.loads(data)
        if time.time() > sig.get("valid_until", 0):
            return None
        return sig
    except Exception as e:
        logger.error(f"Live signal read failed {coin}: {e}")
        return None


class SignalEngineStrategy(IStrategy):

    INTERFACE_VERSION = 3

    stoploss   = -0.99
    timeframe  = "1d"
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
        lev = int(os.getenv("LEVERAGE", 10))
        return min(float(lev), max_leverage)

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
        pair = metadata.get("pair", "")
        coin = pair.replace("/USDT", "").replace(":USDT", "")

        dataframe["enter_long"]  = 0
        dataframe["enter_short"] = 0
        dataframe["enter_tag"]   = ""

        is_backtest = self.dp.runmode.value in ("backtest", "hyperopt", "plot")

        for idx in range(len(dataframe)):
            candle = dataframe.iloc[idx]
            ts     = candle.name

            if is_backtest:
                date_str = ts.strftime("%Y-%m-%d") if hasattr(ts, 'strftime') else str(ts)[:10]
                signal   = _get_backtest_signal(coin, date_str)
            else:
                signal = _get_live_signal(coin)

            if not signal:
                continue

            grade     = signal.get("grade", "F")
            direction = signal.get("direction", "")
            entry     = float(signal.get("entry", 0))
            signal_id = signal.get("signal_id", "")

            if grade not in ["A+", "A", "B"]:
                continue

            if direction == "LONG":
                dataframe.loc[dataframe.index[idx], "enter_long"] = 1
                dataframe.loc[dataframe.index[idx], "enter_tag"]  = f"SE_{grade}_{signal_id}"
            elif direction == "SHORT":
                dataframe.loc[dataframe.index[idx], "enter_short"] = 1
                dataframe.loc[dataframe.index[idx], "enter_tag"]   = f"SE_{grade}_{signal_id}"

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"]  = 0
        dataframe["exit_short"] = 0
        return dataframe

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float, **kwargs) -> float:
        coin = pair.replace("/USDT", "").replace(":USDT", "")
        try:
            is_backtest = self.dp.runmode.value in ("backtest", "hyperopt", "plot")

            if is_backtest:
                date_str = trade.open_date_utc.strftime("%Y-%m-%d")
                signal   = _get_backtest_signal(coin, date_str)
            else:
                signal = _get_live_signal(coin)

            if not signal:
                return self.stoploss

            sl_price = float(signal.get("stoploss", 0) or signal.get("sl", 0))
            if not sl_price or not trade.open_rate:
                return self.stoploss

            if trade.is_short:
                sl_pct = -abs((sl_price - trade.open_rate) / trade.open_rate)
            else:
                sl_pct = (sl_price - trade.open_rate) / trade.open_rate

            sl_pct = max(-0.99, min(-0.001, sl_pct))
            return sl_pct

        except Exception as e:
            logger.error(f"custom_stoploss error {coin}: {e}")
            return self.stoploss

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs) -> Optional[str]:
        coin = pair.replace("/USDT", "").replace(":USDT", "")
        try:
            is_backtest = self.dp.runmode.value in ("backtest", "hyperopt", "plot")

            if is_backtest:
                date_str = trade.open_date_utc.strftime("%Y-%m-%d")
                signal   = _get_backtest_signal(coin, date_str)
            else:
                signal = _get_live_signal(coin)

            if not signal:
                return None

            tp = float(signal.get("tp1", 0) or signal.get("tp", 0))
            if not tp:
                return None

            if not trade.is_short and current_rate >= tp:
                return "tp_hit"
            if trade.is_short and current_rate <= tp:
                return "tp_hit"

        except Exception as e:
            logger.error(f"custom_exit error {coin}: {e}")
        return None

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float,
                            rate: float, time_in_force: str, current_time: datetime,
                            entry_tag: Optional[str], side: str, **kwargs) -> bool:
        is_backtest = self.dp.runmode.value in ("backtest", "hyperopt", "plot")
        if is_backtest:
            return True

        coin = pair.replace("/USDT", "").replace(":USDT", "")
        try:
            signal = _get_live_signal(coin)
            if not signal:
                return False

            import time
            if time.time() > signal.get("valid_until", 0):
                return False

            grade = signal.get("grade", "F")
            if grade not in ["A+", "A", "B"]:
                return False

            entry_price = float(signal.get("entry", 0))
            if entry_price and rate:
                deviation = abs(rate - entry_price) / entry_price
                if deviation > 0.005:
                    return False

            return True

        except Exception as e:
            logger.error(f"confirm_trade_entry error {coin}: {e}")
            return False

    def confirm_trade_exit(self, pair: str, trade: Trade, order_type: str,
                           amount: float, rate: float, time_in_force: str,
                           exit_reason: str, current_time: datetime, **kwargs) -> bool:
        return True