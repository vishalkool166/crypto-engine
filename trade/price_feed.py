import asyncio
import json
import logging
import websockets
from typing import Callable, Dict

log = logging.getLogger(__name__)

BINANCE_WS = "wss://fstream.binance.com/ws"


class PriceFeed:

    def __init__(self):
        self._prices:      Dict[str, float] = {}
        self._callbacks:   list             = []
        self._running:     bool             = False
        self._task:        asyncio.Task     = None
        self._coin:        str              = None
        self._milestones:  set              = set()

    def get_price(self, coin: str) -> float:
        return self._prices.get(coin, 0.0)

    def on_price(self, callback: Callable):
        self._callbacks.append(callback)

    def reset_milestones(self):
        self._milestones = set()
        log.info("Price milestones reset")

    async def start(self, coin: str):
        if self._running and self._coin == coin:
            return
        await self.stop()
        self._coin       = coin
        self._running    = True
        self._milestones = set()
        self._task       = asyncio.create_task(self._stream(coin))
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
        self._coin       = None
        self._milestones = set()
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
                            log.info(f"Price received: {coin} {price}")

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
                    log.warning(f"WS disconnected: {e} — reconnecting in 3s")
                    await asyncio.sleep(3)
                else:
                    break

        log.info(f"Price feed ended: {coin}")

    async def _check_milestones(self, coin: str, price: float):
        from trade.state import state_manager
        from alerts.telegram import send_progress_update

        trade = state_manager.current_trade
        if not trade or trade.coin != coin:
            return

        entry   = trade.entry_price
        tp1     = trade.tp1_price
        sl      = trade.sl_price
        is_long = trade.direction == "LONG"

        if not entry or not tp1 or not sl:
            return

        # Only track phase 1 — entry to TP1
        # Phase 2 milestones not needed — already risk free
        tp1_already_hit = (
            abs(sl - entry) / entry < 0.001
            if sl and entry else False
        )
        if tp1_already_hit:
            return

        total = abs(tp1 - entry)
        if total == 0:
            return

        if is_long:
            progress = (price - entry) / total * 100
        else:
            progress = (entry - price) / total * 100

        # Only fire on positive progress toward TP1
        if progress <= 0:
            return

        for milestone in [25, 50, 75]:
            if progress >= milestone and milestone not in self._milestones:
                self._milestones.add(milestone)
                log.info(
                    f"Milestone {milestone}% reached: "
                    f"{coin} @ {price}"
                )
                try:
                    await send_progress_update(
                        trade         = trade,
                        current_price = price,
                        milestone_pct = milestone
                    )
                except Exception as e:
                    log.error(f"Progress update error: {e}")


price_feed = PriceFeed()