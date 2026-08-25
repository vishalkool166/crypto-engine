from typing import TypedDict, Optional


class SignalAgentState(TypedDict):
    coin:            str
    balance:         float
    df_4h:           object
    df_1h:           object
    df_15m:          object
    df_1d:           object
    df_1w:           object
    d4h:             dict
    d1h:             dict
    d15m:            dict
    atr_4h:          float
    atr_1h:          float
    atr_15m:         float
    regime_result:   object
    trend_result:    object
    reversion_result:object
    ict_result:      object
    risk_result:     object
    sizing_result:   object
    direction:       str
    regime_label:    str
    regime_mult:     float
    trend_strength:  float
    reversion_open:  bool
    session:         str
    score:           float
    grade:           str
    ml_probability:  Optional[float]
    signal:          bool
    reason:          str
    trace_steps:     list
    final_result:    dict