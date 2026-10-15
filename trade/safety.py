"""Pure order-risk validation; opening exposure fails closed."""
import math
import os

LIVE_OPT_IN = 'I_UNDERSTAND_REAL_ORDERS'


def ensure_live_opt_in(mode: str) -> None:
    if mode == 'live' and os.environ.get('SIGNAL_ENGINE_ALLOW_LIVE_TRADING') != LIVE_OPT_IN:
        raise PermissionError('Live order execution disabled; operator opt-in required')


def validate_entry(direction: str, entry: float, sl: float, tp: float, stake: float,
                   leverage: int, minimum_stake: float) -> None:
    values = (entry, sl, tp, stake)
    if not all(isinstance(v, (int, float)) and math.isfinite(v) and v > 0 for v in values):
        raise ValueError('Entry, stop, target and stake must be finite positive numbers')
    if not isinstance(leverage, int) or isinstance(leverage, bool) or not 1 <= leverage <= 20:
        raise ValueError('Leverage must be an integer from 1 to 20')
    if stake < minimum_stake:
        raise ValueError('Stake below minimum')
    if direction == 'LONG' and not (sl < entry < tp):
        raise ValueError('LONG trade requires SL < entry < TP')
    if direction == 'SHORT' and not (tp < entry < sl):
        raise ValueError('SHORT trade requires TP < entry < SL')
    if direction not in ('LONG', 'SHORT'):
        raise ValueError('Direction must be LONG or SHORT')


def require_precision(info: dict) -> None:
    for key in ('step_size', 'tick_size', 'min_qty'):
        value = info.get(key)
        if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f'Exchange precision unavailable: {key}; blocking order')


def validate_symbol_notional(price: float, quantity: float, min_notional: float) -> None:
    """Reject new positions under the exchange's symbol-specific notional floor.

    The floor comes from a current exchangeInfo MIN_NOTIONAL filter. Missing or
    invalid metadata is an error rather than an assumed $5 minimum.
    """
    if not all(isinstance(x, (float, int)) and math.isfinite(x) and x > 0
               for x in (price, quantity, min_notional)):
        raise ValueError("Exchange minimum notional unavailable or invalid")
    if price * quantity + 1e-9 < min_notional:
        raise ValueError(f"Order notional below exchange minimum {min_notional}")
