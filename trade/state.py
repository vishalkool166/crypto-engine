# trade/state.py — compatibility stub
# trade/ folder was removed in Phase 1.
# This stub exists only to satisfy imports in
# engines/signal.py check_correlation() function.
# Do not add real logic here.

import logging
log = logging.getLogger(__name__)


class _StateManagerStub:
    is_idle       = True
    is_paused     = False
    current_trade = None
    active_trades = {}

    def can_open_trade(self) -> bool:
        return False

    def health_state_for(self, trade_id) -> str:
        return "HEALTHY"

    def health_data_for(self, trade_id) -> dict:
        return {
            "failures": [],
            "warnings": [],
            "checks":   [],
            "summary":  ""
        }

    def is_tp1_hit_for(self, trade_id) -> bool:
        return False

    def refresh(self):
        pass

    def pause(self):
        pass

    def resume(self):
        pass


state_manager = _StateManagerStub()