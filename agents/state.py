from typing import TypedDict, Optional


class SignalAgentState(TypedDict):
    coin:          str
    balance:       float
    df_4h:         object
    df_1h:         object
    d4h:           dict
    d1h:           dict
    atr_4h:        float
    atr_1h:        float
    regime_result: object
    trend_result:  object
    risk_result:   object
    sizing_result: object
    direction:     str
    regime_label:  str
    regime_mult:   float
    session:       str
    score:         float
    grade:         str
    signal:        bool
    reason:        str
    trace_steps:   list
    final_result:  dict