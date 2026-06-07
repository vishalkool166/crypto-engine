import asyncio
import json
import logging
import websockets
from typing import Callable, Dict

log = logging.getLogger(__name__)

BINANCE_WS = "wss://fstream.binance.com/ws"


class PriceFeed:

    def __init__(self):
        self._prices:    Dict[str, float] = {}
        self._callbacks: list             = []
        self._running:   bool             = False
        self._task:      asyncio.Task     = None
        self._coin:      str              = None

    def get_price(self, coin: str) -> float:
        return self._prices.get(coin, 0.0)

    def on_price(self, callback: Callable):
        self._callbacks.append(callback)

    async def start(self, coin: str):
        if self._running and self._coin == coin:
            return
        await self.stop()
        self._coin    = coin
        self._running = True
        self._task    = asyncio.create_task(self._stream(coin))
        log.info(f"Price feed started: {coin}")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self._coin = None
        log.info("Price feed stopped")

    async def _stream(self, coin: str):
        stream = f"{coin.lower()}usdt@markPrice@1s"
        url    = f"{BINANCE_WS}/{stream}"

        while self._running:
            try:
                async with websockets.connect(
                    url,
                    ping_interval = 20,
                    ping_timeout  = 10
                ) as ws:
                    log.info(f"WS connected: {stream}")
                    async for raw in ws:
                        if not self._running:
                            break
                        try:
                            data  = json.loads(raw)
                            price = float(data["p"])
                            self._prices[coin] = price
                            for cb in self._callbacks:
                                try:
                                    await cb(coin, price)
                                except Exception as e:
                                    log.error(f"Price callback error: {e}")
                        except Exception as e:
                            log.error(f"WS parse error: {e}")
                            continue

            except asyncio.CancelledError:
                break
            except Exception as e:
                if self._running:
                    log.warning(f"WS disconnected: {e} — reconnecting in 3s")
                    await asyncio.sleep(3)
                else:
                    break

        log.info(f"Price feed ended: {coin}")


price_feed = PriceFeed()