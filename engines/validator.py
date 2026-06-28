import pandas as pd
import logging

log = logging.getLogger(__name__)

TF_MINUTES = {
    "1w":  10080,
    "1d":  1440,
    "4h":  240,
    "1h":  60,
    "15m": 15
}

MAX_SINGLE_CANDLE_MOVE = 0.50

MIN_VIABLE_CANDLES = {
    "1w":  20,
    "1d":  50,
    "4h":  50,
    "1h":  50,
    "15m": 20
}


def validate_candles(
    df:   pd.DataFrame,
    coin: str,
    tf:   str
) -> dict:

    issues = []

    if df is None or df.empty:
        return {
            "df":       df,
            "valid":    False,
            "clean":    False,
            "issues":   ["Empty or null dataframe"],
            "original": 0,
            "cleaned":  0,
            "removed":  0
        }

    original_len = len(df)
    df = df.copy()

    for col in ["open", "high", "low", "close", "volume"]:
        if col not in df.columns:
            return {
                "df":       df,
                "valid":    False,
                "clean":    False,
                "issues":   [f"Missing column: {col}"],
                "original": original_len,
                "cleaned":  len(df),
                "removed":  0
            }
        df[col] = pd.to_numeric(df[col], errors="coerce")

    before = len(df)
    df = df.dropna(subset=["open", "high", "low", "close", "volume"])
    removed_nan = before - len(df)
    if removed_nan > 0:
        issues.append(f"NaN values removed: {removed_nan} rows")
        log.warning(f"NaN candles removed: {coin} {tf} — {removed_nan} rows")

    if df.index.duplicated().any():
        count = df.index.duplicated().sum()
        issues.append(f"Duplicate timestamps: {count}")
        log.warning(f"Duplicate timestamps: {coin} {tf} — {count} rows")
        df = df[~df.index.duplicated(keep="last")]

    ohlcv_cols  = ["open", "high", "low", "close", "volume"]
    ohlcv_dupes = df.duplicated(subset=ohlcv_cols, keep="first")
    if ohlcv_dupes.any():
        count = ohlcv_dupes.sum()
        issues.append(f"Duplicate OHLCV rows: {count}")
        log.warning(f"Duplicate OHLCV rows: {coin} {tf} — {count} rows")
        df = df[~ohlcv_dupes]

    invalid_hl = df["high"] < df["low"]
    if invalid_hl.any():
        count = invalid_hl.sum()
        issues.append(f"High < Low violations: {count}")
        log.warning(f"High < Low: {coin} {tf} — {count} rows")
        df = df[~invalid_hl]

    invalid_close = (df["close"] > df["high"]) | (df["close"] < df["low"])
    if invalid_close.any():
        count = invalid_close.sum()
        issues.append(f"Close outside High/Low range: {count}")
        log.warning(f"Close outside range: {coin} {tf} — {count} rows")
        df = df[~invalid_close]

    invalid_open = (df["open"] > df["high"]) | (df["open"] < df["low"])
    if invalid_open.any():
        count = invalid_open.sum()
        issues.append(f"Open outside High/Low range: {count}")
        log.warning(f"Open outside range: {coin} {tf} — {count} rows")
        df = df[~invalid_open]

    zero_prices = (
        (df["open"]  <= 0) |
        (df["high"]  <= 0) |
        (df["low"]   <= 0) |
        (df["close"] <= 0)
    )
    if zero_prices.any():
        count = zero_prices.sum()
        issues.append(f"Zero/negative prices: {count}")
        log.warning(f"Zero/negative prices: {coin} {tf} — {count} rows")
        df = df[~zero_prices]

    neg_vol = df["volume"] < 0
    if neg_vol.any():
        count = neg_vol.sum()
        issues.append(f"Negative volume: {count}")
        log.warning(f"Negative volume: {coin} {tf} — {count} rows")
        df = df[~neg_vol]

    if len(df) > 1:
        pct_change = df["close"].pct_change().abs()
        extreme    = pct_change[pct_change > MAX_SINGLE_CANDLE_MOVE].dropna()
        if len(extreme) > 0:
            issues.append(
                f"Extreme candle moves (>{MAX_SINGLE_CANDLE_MOVE*100:.0f}%): "
                f"{len(extreme)} candles — review manually"
            )
            log.warning(
                f"Extreme moves: {coin} {tf} — "
                f"{len(extreme)} candles — "
                f"max: {pct_change.max()*100:.1f}%"
            )

    expected_gap = TF_MINUTES.get(tf)
    if expected_gap and len(df) > 1:
        try:
            if not pd.api.types.is_datetime64_any_dtype(df.index):
                log.debug(f"Gap detection skipped: {coin} {tf} — index is not datetime")
            else:
                time_diffs = df.index.to_series().diff().dt.total_seconds() / 60
                large_gaps = time_diffs[time_diffs > expected_gap * 2].dropna()
                if len(large_gaps) > 0:
                    issues.append(
                        f"Possible missing candles: {len(large_gaps)} gaps "
                        f"(>{expected_gap * 2}min)"
                    )
                    log.warning(
                        f"Missing candles: {coin} {tf} — "
                        f"{len(large_gaps)} gaps detected"
                    )
        except Exception as e:
            log.debug(f"Gap detection skipped: {coin} {tf} — {e}")

    df = df.sort_index()

    cleaned_len  = len(df)
    removed      = original_len - cleaned_len
    min_required = MIN_VIABLE_CANDLES.get(tf, 50)
    is_valid     = cleaned_len >= min_required

    if not is_valid:
        issues.append(
            f"Insufficient candles after cleaning: "
            f"{cleaned_len} (need {min_required})"
        )
        log.error(
            f"Validation failed: {coin} {tf} — "
            f"only {cleaned_len} candles after cleaning"
        )

    if removed > 0:
        log.info(
            f"Validation complete: {coin} {tf} — "
            f"{original_len} → {cleaned_len} candles "
            f"({removed} removed)"
        )

    return {
        "df":       df,
        "valid":    is_valid,
        "clean":    len(issues) == 0,
        "issues":   issues,
        "original": original_len,
        "cleaned":  cleaned_len,
        "removed":  removed
    }


def validate_all_timeframes(
    klines: dict,
    coin:   str
) -> dict:

    cleaned_klines = {}
    reports        = {}
    errors         = []

    for tf, df in klines.items():
        result = validate_candles(df, coin, tf)
        reports[tf] = result

        if not result["valid"]:
            errors.append(f"{tf}: {' | '.join(result['issues'])}")
            log.error(f"Validation FAILED: {coin} {tf}")
        else:
            cleaned_klines[tf] = result["df"]
            if result["issues"]:
                log.info(
                    f"Validation passed with warnings: "
                    f"{coin} {tf} — {result['issues']}"
                )

    return {
        "valid":   len(errors) == 0,
        "klines":  cleaned_klines,
        "reports": reports,
        "errors":  errors
    }