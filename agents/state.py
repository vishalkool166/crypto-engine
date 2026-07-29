from typing import TypedDict, Optional


class SignalAgentState(TypedDict):
    coin:            str
    balance:         float
    df_4h:           object
    df_1h:           object
    df_15m:          object
    df_1d:           object
    df_1w:           object
    direction:       str
    atr_4h:          float
    atr_1h:          float
    atr_15m:         float
    d4h:             dict
    d1h:             dict
    d15m:            dict
    regime:          str
    session:         str
    ctx:             dict
    sweep_result:    dict
    zone_result:     dict
    trigger_result:  dict
    risk_result:     dict
    sizing_result:   dict
    score:           float
    grade:           str
    ml_probability:  Optional[float]
    signal:          bool
    reason:          str
    trace_steps:     list
    final_result:    dict