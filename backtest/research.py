"""Reproducible Binance USD-M futures research data acquisition and replay.

No API key, no trading capabilities. Explicit date ranges, validated OHLCV,
funding settlements, retry-on-429/5xx, saved local CSV and SHA-256 hashes.
Example:
    python -m backtest.research download --coins ETH,SOL --start 2023-01-01 --end 2026-01-01
    python -m backtest.research evaluate --coins ETH,SOL --data-dir research_data
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

import pandas as pd
import requests

from backtest.engine import _load_csv, _utc_index, run_backtest, ReplayCosts
from config import COIN_CONFIG

BASE_URL = 'https://fapi.binance.com'
HARD_RETRY_LIMIT = 5


def _json(session: requests.Session, path: str, params: dict):
    for attempt in range(HARD_RETRY_LIMIT):
        try:
            response = session.get(BASE_URL + path, params=params, timeout=(5, 25))
            if response.status_code == 418:
                # Binance 418 is an IP ban. Retrying during a ban extends or
                # exacerbates the restriction; do not hammer the service.
                response.raise_for_status()
            if response.status_code == 429 or response.status_code >= 500:
                if attempt + 1 == HARD_RETRY_LIMIT:
                    response.raise_for_status()
                retry_after = response.headers.get('Retry-After', '')
                try:
                    wait = min(60.0, max(1.0, float(retry_after)))
                except ValueError:
                    wait = min(60, 2 ** attempt)
                time.sleep(wait)
                continue
            response.raise_for_status()
            return response.json()
        except (requests.Timeout, requests.ConnectionError):
            if attempt == HARD_RETRY_LIMIT - 1:
                raise
            time.sleep(min(30, 2 ** attempt))
    raise RuntimeError('Request failed without valid response')


def _utc_ms(value: str) -> int:
    return int(pd.Timestamp(value, tz='UTC').timestamp() * 1000)


def fetch_klines(symbol: str, interval: str, start_ms: int, end_ms: int,
                 session: requests.Session | None = None) -> pd.DataFrame:
    if interval not in ('1h', '4h'):
        raise ValueError('Research supports only 1h and 4h candles')
    step = 3600000 if interval == '1h' else 14400000
    if start_ms % step or end_ms % step:
        raise ValueError(f'{symbol} {interval}: UTC window must align to candle boundaries')
    session = session or requests.Session()
    rows = []
    cursor = start_ms
    while cursor < end_ms:
        chunk = _json(session, '/fapi/v1/klines', {
            'symbol': symbol, 'interval': interval, 'startTime': cursor,
            'endTime': end_ms - 1, 'limit': 1000,
        })
        if not chunk:
            break
        for k in chunk:
            ts = int(k[0])
            if ts + step > int(time.time() * 1000):
                raise ValueError(f'{symbol} {interval}: Binance returned an unfinished candle')
            if start_ms <= ts < end_ms:
                rows.append([ts, float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])])
        nxt = int(chunk[-1][0]) + step
        if nxt <= cursor:
            raise RuntimeError('Binance returned non-advancing candle pagination')
        cursor = nxt
        time.sleep(0.08)
    if not rows:
        raise ValueError(f'{symbol} {interval}: no candles in requested range')
    df = pd.DataFrame(rows, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    df = _utc_index(df.set_index('timestamp'))
    if (df.index.to_series().diff().dropna() != pd.Timedelta(milliseconds=step)).any():
        raise ValueError(f'{symbol} {interval} missing candles; refusing incomplete sample')
    if df.index[0].value // 1_000_000 > start_ms + step or df.index[-1].value // 1_000_000 < end_ms - step:
        raise ValueError(f'{symbol} {interval} partial history; verify listing date and date range')
    return df


def fetch_funding(symbol: str, start_ms: int, end_ms: int,
                  session: requests.Session | None = None) -> pd.DataFrame:
    session = session or requests.Session()
    rows = []
    cursor = start_ms
    while cursor < end_ms:
        chunk = _json(session, '/fapi/v1/fundingRate', {
            'symbol': symbol, 'startTime': cursor, 'endTime': end_ms - 1, 'limit': 1000,
        })
        if not chunk:
            break
        for item in chunk:
            ts = int(item['fundingTime'])
            if ts < end_ms:
                rows.append((ts, float(item['fundingRate'])))
        nxt = int(chunk[-1]['fundingTime']) + 1
        if nxt <= cursor:
            raise RuntimeError('Binance returned non-advancing funding pagination')
        cursor = nxt
        time.sleep(0.08)
    df = pd.DataFrame(rows, columns=['timestamp', 'funding_rate'])
    if df.empty:
        raise ValueError(f'{symbol}: no funding settlements in sample')
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    return df.set_index('timestamp').sort_index()


def download(coin: str, start: str, end: str, directory: Path) -> dict:
    if coin not in COIN_CONFIG:
        raise ValueError(f'{coin} not configured')
    if pd.Timestamp(end) <= pd.Timestamp(start):
        raise ValueError('End must be later than start')
    first, last = _utc_ms(start), _utc_ms(end)
    directory.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    hashes = {}
    for tf in ('4h', '1h'):
        df = fetch_klines(coin + 'USDT', tf, first, last, session)
        file = directory / f'{coin}_{tf}.csv'
        df.to_csv(file, index_label='timestamp')
        hashes[file.name] = hashlib.sha256(file.read_bytes()).hexdigest()
    funding = fetch_funding(coin + 'USDT', first, last, session)
    file = directory / f'{coin}_funding.csv'
    funding.to_csv(file, index_label='timestamp')
    hashes[file.name] = hashlib.sha256(file.read_bytes()).hexdigest()
    meta = {'coin': coin, 'symbol': coin + 'USDT', 'source': BASE_URL,
            'start': start, 'end_exclusive': end, 'sha256': hashes}
    (directory / f'{coin}_manifest.json').write_text(json.dumps(meta, indent=2) + '\n')
    return meta


def _verify_manifest_times(coin: str, manifest: dict, candles_4h: pd.DataFrame,
                           candles_1h: pd.DataFrame, funding: pd.DataFrame) -> None:
    """Hash integrity alone cannot prove sample completeness or funding coverage."""
    try:
        start = pd.Timestamp(manifest['start'])
        end = pd.Timestamp(manifest['end_exclusive'])
        start = start.tz_localize('UTC') if start.tzinfo is None else start.tz_convert('UTC')
        end = end.tz_localize('UTC') if end.tzinfo is None else end.tz_convert('UTC')
    except (KeyError, ValueError, TypeError) as exc:
        raise ValueError(f'{coin}: invalid manifest dates') from exc
    if not start < end or end > pd.Timestamp.now(tz='UTC'):
        raise ValueError(f'{coin}: manifest period must be complete and chronological')
    for tf, frame, step in (('4h', candles_4h, pd.Timedelta(hours=4)),
                            ('1h', candles_1h, pd.Timedelta(hours=1))):
        if frame.empty or frame.index[0] != start or frame.index[-1] + step != end:
            raise ValueError(f'{coin}: {tf} sample does not cover exact manifest period')
        if (frame.index.to_series().diff().dropna() != step).any():
            raise ValueError(f'{coin}: {tf} contains missing or irregular candles')
    if funding.empty or funding.index[0] < start or funding.index[-1] >= end:
        raise ValueError(f'{coin}: funding timestamps outside manifest period')
    # Funding is usually settled several times per day. If all earlier/later
    # settlements are missing, counting the observed subset is not enough.
    bound = pd.Timedelta(hours=24)
    if funding.index[0] - start > bound or end - funding.index[-1] > bound or \
       (funding.index.to_series().diff().dropna() > bound).any():
        raise ValueError(f'{coin}: incomplete funding settlement coverage')


def evaluate(coin: str, directory: Path, research_min_score: float = 50,
             signal_start: str | None = None, signal_end: str | None = None) -> dict:
    manifest_file = directory / f'{coin}_manifest.json'
    if not manifest_file.is_file():
        raise FileNotFoundError(f'{coin}: missing dataset manifest; run research download first')
    manifest = json.loads(manifest_file.read_text())
    if manifest.get('coin') != coin or manifest.get('symbol') != coin + 'USDT':
        raise ValueError('Manifest symbol mismatch')
    required = {f'{coin}_4h.csv', f'{coin}_1h.csv', f'{coin}_funding.csv'}
    hashes = manifest.get('sha256', {})
    if not required.issubset(hashes):
        raise ValueError(f'{coin}: missing required candle/funding checksums')
    for fname in required:
        actual = hashlib.sha256((directory / fname).read_bytes()).hexdigest()
        if actual != hashes[fname]:
            raise ValueError(f'Dataset checksum mismatch: {fname}')
    # Funding is mandatory for an after-cost futures comparison. An absent
    # funding series used to silently make profitable-looking results.
    funding_file = directory / f'{coin}_funding.csv'
    funding = pd.read_csv(funding_file)
    if not {'timestamp', 'funding_rate'}.issubset(funding.columns):
        raise ValueError(f'{coin}: invalid funding schema')
    funding['timestamp'] = pd.to_datetime(funding['timestamp'], utc=True)
    funding['funding_rate'] = pd.to_numeric(funding['funding_rate'], errors='raise')
    if funding.empty or not funding['funding_rate'].map(lambda v: pd.notna(v) and abs(v) < 1).all():
        raise ValueError(f'{coin}: missing or invalid funding data')
    funding = funding.set_index('timestamp').sort_index()
    if funding.index.has_duplicates:
        raise ValueError(f'{coin}: duplicate funding timestamps')
    candles_4h = _load_csv(directory / f'{coin}_4h.csv')
    candles_1h = _load_csv(directory / f'{coin}_1h.csv')
    _verify_manifest_times(coin, manifest, candles_4h, candles_1h, funding)
    if signal_start is not None or signal_end is not None:
        actual_start, actual_end = candles_4h.index[0], candles_4h.index[-1] + pd.Timedelta(hours=4)
        for label, bound in (('signal_start', signal_start), ('signal_end', signal_end)):
            if bound is not None:
                ts = pd.Timestamp(bound)
                ts = ts.tz_localize('UTC') if ts.tzinfo is None else ts.tz_convert('UTC')
                if ts < actual_start or ts > actual_end:
                    raise ValueError(f'{coin}: {label} lies outside verified dataset coverage')
    return run_backtest(coin, df_4h=candles_4h,
                        df_1h=candles_1h,
                        funding=funding, persist=False,
                        research_min_score=research_min_score,
                        signal_start=signal_start, signal_end=signal_end)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['download', 'evaluate', 'compare'])
    parser.add_argument('--coins', default='ETH,SOL')
    parser.add_argument('--start', default='2023-01-01')
    parser.add_argument('--end', default='2026-01-01')
    parser.add_argument('--data-dir', default='research_data')
    args = parser.parse_args()
    coins = [c.strip().upper() for c in args.coins.split(',') if c.strip()]
    outdir = Path(args.data_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    results = []
    for coin in coins:
        try:
            if args.action == 'download':
                result = download(coin, args.start, args.end, outdir)
            elif args.action == 'compare':
                result = {'coin': coin, 'baseline': evaluate(coin, outdir, 50),
                          'research_40': evaluate(coin, outdir, 40)}
                result['baseline'].pop('trades', None)
                result['research_40'].pop('trades', None)
            else:
                result = evaluate(coin, outdir)
            results.append(result)
            print(coin, json.dumps({k: v for k, v in result.items() if k not in ('trades', 'by_grade')}, default=str)[:4000])
        except Exception as exc:
            results.append({'coin': coin, 'error': str(exc)})
            print(f'{coin}: ERROR {exc}')
    (outdir / f'{args.action}_results.json').write_text(json.dumps(results, indent=2, default=str))


if __name__ == '__main__':
    main()
