import json
import logging
import os
import requests
from datetime import datetime, timezone
from typing import Optional
from freqtrade.strategy import IStrategy, stoploss_from_open
from freqtrade.persistence import Trade
from pandas import DataFrame

logger = logging.getLogger(__name__)

_redis_client  = None
_locked_levels = {}


def _get_redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        import redis
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


def _get_signal_from_db(signal_id: int) -> dict | None:
    try:
        response = requests.get(
            f"http://signal-engine:8000/api/signal/{signal_id}",
            timeout=5
        )
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        logger.error(f"DB signal fetch failed id:{signal_id}: {e}")
    return None


def _get_signal_levels(trade: Trade) -> dict | None:
    try:
        enter_tag = getattr(trade, "enter_tag", "") or ""
        logger.info(f"_get_signal_levels: pair={trade.pair} enter_tag={enter_tag}")

        if enter_tag.startswith("SE_"):
            parts = enter_tag.split("_")
            if len(parts) >= 3:
                signal_id = int(parts[-1])
                sig = _get_signal_from_db(signal_id)
                if sig:
                    sl    = sig.get("sl")
                    tp1   = sig.get("tp1")
                    entry = sig.get("entry")
                    if sl and float(sl) > 0 and tp1 and float(tp1) > 0:
                        logger.info(
                            f"Signal {signal_id} loaded: "
                            f"sl={sl} tp1={tp1} entry={entry}"
                        )
                        return {"sl": sl, "tp1": tp1, "entry": entry}

        coin = trade.pair.replace("/USDT:USDT", "").replace("/USDT", "")
        r    = _get_redis()
        if r:
            import time
            data = r.get(f"signal:{coin}USDT")
            if data:
                sig = json.loads(data)
                if time.time() <= sig.get("valid_until", 0):
                    sl    = sig.get("sl")
                    tp1   = sig.get("tp1")
                    entry = sig.get("entry")
                    if sl and float(sl) > 0 and tp1 and float(tp1) > 0:
                        logger.info(
                            f"Redis fallback successful for {coin} "
                            f"sl={sl} tp1={tp1}"
                        )
                        return {"sl": sl, "tp1": tp1, "entry": entry}

        logger.warning(
            f"No valid signal levels found for {trade.pair} "
            f"enter_tag={enter_tag}"
        )
        return None

    except Exception as e:
        logger.error(f"_get_signal_levels error: {e}")
        return None


class SignalEngineStrategy(IStrategy):

    INTERFACE_VERSION = 3

    stoploss                      = -0.99
    timeframe                     = "5m"
    can_short                     = True
    use_custom_stoploss           = True
    stoploss_on_exchange          = os.getenv("TRADING_MODE", "paper") == "live"
    stoploss_on_exchange_interval = 60

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

    def leverage(
        self,
        pair:              str,
        current_time:      datetime,
        current_rate:      float,
        proposed_leverage: float,
        max_leverage:      float,
        entry_tag:         Optional[str],
        side:              str,
        **kwargs
    ) -> float:
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
                        _push_funding_to_redis(
                            coin,
                            float(result.get("fundingRate", 0))
                        )
                except Exception as e:
                    logger.warning(f"Funding push failed {coin}: {e}")

                try:
                    result = self.dp._exchange._api.fetch_open_interest(pair)
                    if result:
                        _push_oi_to_redis(
                            coin,
                            float(result.get("openInterestAmount", 0))
                        )
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
        dataframe["enter_tag"]   = ""
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"]  = 0
        dataframe["exit_short"] = 0
        return dataframe

    def custom_stoploss(
        self,
        pair:           str,
        trade:          Trade,
        current_time:   datetime,
        current_rate:   float,
        current_profit: float,
        **kwargs
    ) -> float:
        try:
            if trade.id in _locked_levels:
                levels = _locked_levels[trade.id]
            else:
                levels = _get_signal_levels(trade)
                if levels:
                    _locked_levels[trade.id] = levels
                    logger.info(
                        f"Levels locked for trade {trade.id} "
                        f"{pair}: sl={levels['sl']} tp1={levels['tp1']}"
                    )

            if not levels:
                return self.stoploss

            sl_price  = float(levels.get("sl") or 0)
            open_rate = trade.open_rate

            if not sl_price or not open_rate:
                return self.stoploss

            if trade.is_short:
                open_relative_stop = (sl_price - open_rate) / open_rate
            else:
                open_relative_stop = -((open_rate - sl_price) / open_rate)

            result = stoploss_from_open(
                open_relative_stop = open_relative_stop,
                current_profit     = current_profit,
                is_short           = trade.is_short,
                leverage           = trade.leverage
            )

            if result == 1:
                return self.stoploss

            return result

        except Exception as e:
            logger.error(f"custom_stoploss error {pair}: {e}")
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
        try:
            if trade.id in _locked_levels:
                levels = _locked_levels[trade.id]
            else:
                levels = _get_signal_levels(trade)
                if levels:
                    _locked_levels[trade.id] = levels
                    logger.info(
                        f"Levels locked for trade {trade.id} "
                        f"{pair}: sl={levels['sl']} tp1={levels['tp1']}"
                    )

            if not levels:
                return None

            tp = float(levels.get("tp1") or 0)
            if not tp:
                return None

            if not trade.is_short and current_rate >= tp:
                logger.info(f"TP hit: {pair} rate={current_rate} tp={tp}")
                _locked_levels.pop(trade.id, None)
                return "tp_hit"

            if trade.is_short and current_rate <= tp:
                logger.info(f"TP hit: {pair} rate={current_rate} tp={tp}")
                _locked_levels.pop(trade.id, None)
                return "tp_hit"

        except Exception as e:
            logger.error(f"custom_exit error {pair}: {e}")

        return None

    def confirm_trade_entry(
        self,
        pair:          str,
        order_type:    str,
        amount:        float,
        rate:          float,
        time_in_force: str,
        current_time:  datetime,
        entry_tag:     Optional[str],
        side:          str,
        **kwargs
    ) -> bool:
        return True

    def confirm_trade_exit(
        self,
        pair:          str,
        trade:         Trade,
        order_type:    str,
        amount:        float,
        rate:          float,
        time_in_force: str,
        exit_reason:   str,
        current_time:  datetime,
        **kwargs
    ) -> bool:
        return True