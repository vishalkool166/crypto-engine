import asyncio
import json
import logging
from typing import Callable, Dict, Set

log = logging.getLogger(__name__)

BINANCE_WS = "wss://fstream.binance.com/ws"


class PriceFeed:

    def __init__(self):
        self._prices:     Dict[str, float] = {}
        self._callbacks:  list             = []
        self._running:    bool             = False
        self._tasks:      Dict[str, asyncio.Task] = {}
        self._milestones: Dict[str, Set]   = {}
        self._backoff:    Dict[str, float] = {}

    def get_price(self, coin: str) -> float:
        return self._prices.get(coin, 0.0)

    def on_price(self, callback: Callable):
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def reset_milestones(self, coin: str = None):
        if coin:
            self._milestones[coin] = set()
        else:
            self._milestones.clear()

    async def start(self, coin: str):
        if coin in self._tasks and not self._tasks[coin].done():
            return
        self._running             = True
        self._milestones[coin]    = set()
        self._backoff[coin]       = 3.0
        self._tasks[coin]         = asyncio.create_task(self._stream(coin))
        log.info(f"Price feed started: {coin}")

    async def stop(self):
        self._running = False
        for coin, task in list(self._tasks.items()):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks.clear()
        self._milestones.clear()
        self._backoff.clear()
        log.info("Price feed stopped")

    async def remove_coin(self, coin: str):
        task = self._tasks.pop(coin, None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._milestones.pop(coin, None)
        self._backoff.pop(coin, None)
        log.info(f"Price feed removed: {coin}")

    async def _stream(self, coin: str):
        import websockets
        stream = f"{coin.lower()}usdt@markPrice@1s"
        url    = f"{BINANCE_WS}/{stream}"

        while self._running:
            try:
                async with websockets.connect(
                    url,
                    ping_interval = 20,
                    ping_timeout  = 10,
                    close_timeout = 5
                ) as ws:
                    self._backoff[coin] = 3.0
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

                            await self._check_milestones(coin, price)

                        except Exception as e:
                            log.error(f"WS parse error: {e}")
                            continue

            except asyncio.CancelledError:
                break
            except Exception as e:
                if self._running:
                    delay = self._backoff.get(coin, 3.0)
                    log.warning(f"WS disconnected {coin}: {e} — reconnecting in {delay:.0f}s")
                    await asyncio.sleep(delay)
                    self._backoff[coin] = min(delay * 2, 60.0)
                else:
                    break

        log.info(f"Price feed ended: {coin}")

    async def _check_milestones(self, coin: str, price: float):
        from trade.state import state_manager
        from alerts.telegram import send_progress_update

        trade = None
        for t in state_manager.active_trades.values():
            if t.coin == coin:
                trade = t
                break

        if not trade:
            return

        entry   = trade.entry_price
        tp1     = trade.tp1_price
        sl      = trade.sl_price
        is_long = trade.direction == "LONG"

        if not entry or not tp1 or not sl:
            return

        tp1_already_hit = (
            abs(sl - entry) / entry < 0.001
            if sl and entry else False
        )
        if tp1_already_hit:
            return

        total = abs(tp1 - entry)
        if total == 0:
            return

        progress = (
            (price - entry) / total * 100
            if is_long else
            (entry - price) / total * 100
        )

        if progress <= 0:
            return

        milestones = self._milestones.setdefault(coin, set())
        for milestone in [25, 50, 75]:
            if progress >= milestone and milestone not in milestones:
                milestones.add(milestone)
                try:
                    await send_progress_update(
                        trade         = trade,
                        current_price = price,
                        milestone_pct = milestone
                    )
                except Exception as e:
                    log.error(f"Progress update error: {e}")


price_feed = PriceFeed()