#!/usr/bin/env python3
"""Read-only USDⓈ-M historical market-data export for offline research."""
from __future__ import annotations

import argparse
import ast
import csv
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

BASE_URL = 'https://fapi.binance.com'
INTERVAL_MS = {'1m': 60_000, '5m': 300_000, '15m': 900_000, '1h': 3_600_000, '4h': 14_400_000}
MAX_LIMIT = 1500
USER_AGENT = 'signal-engine-historical-research-export/1.0'


def utc_ms(dt: datetime) -> int:
    return int(dt.astimezone(timezone.utc).timestamp() * 1000)


def read_coin_config(path: Path) -> dict[str, dict]:
    """Read only the COIN_CONFIG literal with AST; do not import runtime secrets."""
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(target, ast.Name) and target.id == 'COIN_CONFIG' for target in targets):
                value = ast.literal_eval(node.value)
                if not isinstance(value, dict) or not value:
                    raise ValueError('COIN_CONFIG must be a non-empty literal dictionary')
                return value
    raise ValueError(f'COIN_CONFIG literal not found in {path}')


def request_json(path: str, params: dict | None = None, retries: int = 7):
    query = urllib.parse.urlencode(params or {})
    url = f'{BASE_URL}{path}' + (f'?{query}' if query else '')
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as exc:
            body = exc.read(1000).decode('utf-8', errors='replace')
            if exc.code == 429 or exc.code >= 500:
                retry_after = exc.headers.get('Retry-After')
                delay = min(120, max(1, int(retry_after))) if retry_after and retry_after.isdigit() else min(60, 2 ** attempt)
                print(f'HTTP {exc.code}; retrying in {delay}s ({body[:200]})', file=sys.stderr)
                time.sleep(delay)
                continue
            raise RuntimeError(f'Binance HTTP {exc.code}: {body}') from exc
        except (TimeoutError, urllib.error.URLError) as exc:
            if attempt + 1 == retries:
                raise RuntimeError(f'Binance request failed after {retries} attempts: {exc}') from exc
            time.sleep(min(60, 2 ** attempt))
    raise RuntimeError('Binance request retries exhausted')


def get_exchange_symbols() -> dict[str, dict]:
    payload = request_json('/fapi/v1/exchangeInfo')
    return {row['symbol']: row for row in payload.get('symbols', [])}


def fetch_klines(symbol: str, interval: str, start_ms: int, end_ms: int) -> list[list]:
    step = INTERVAL_MS[interval]
    cursor = start_ms
    rows: dict[int, list] = {}
    while cursor < end_ms:
        page = request_json('/fapi/v1/klines', {
            'symbol': symbol, 'interval': interval,
            'startTime': cursor, 'endTime': min(end_ms - 1, cursor + step * MAX_LIMIT - 1),
            'limit': MAX_LIMIT,
        })
        if not page:
            break
        for candle in page:
            opened = int(candle[0])
            closed = int(candle[6])
            # Exclude any in-progress candle using Binance's close timestamp.
            if start_ms <= opened < end_ms and closed < int(time.time() * 1000):
                rows[opened] = candle
        next_cursor = int(page[-1][0]) + step
        if next_cursor <= cursor:
            raise RuntimeError(f'Pagination did not advance for {symbol} {interval}')
        cursor = next_cursor
        time.sleep(0.08)
    ordered = [rows[key] for key in sorted(rows)]
    if not ordered:
        raise RuntimeError(f'No completed candles returned for {symbol} {interval}')
    gaps = [
        (int(ordered[i][0]), int(ordered[i + 1][0]))
        for i in range(len(ordered) - 1)
        if int(ordered[i + 1][0]) - int(ordered[i][0]) != step
    ]
    if gaps:
        first = datetime.fromtimestamp(gaps[0][0] / 1000, timezone.utc).isoformat()
        raise RuntimeError(f'{symbol} {interval} has {len(gaps)} candle gaps; first near {first}; refusing incomplete export')
    if ordered[0][0] - start_ms > step:
        raise RuntimeError(f'{symbol} {interval} starts more than one interval after the requested/listing start')
    if end_ms - ordered[-1][0] > 2 * step:
        raise RuntimeError(f'{symbol} {interval} ends more than two intervals before the requested end')
    return ordered


def fetch_funding(symbol: str, start_ms: int, end_ms: int) -> list[dict]:
    cursor = start_ms
    rows: dict[int, dict] = {}
    while cursor < end_ms:
        page = request_json('/fapi/v1/fundingRate', {
            'symbol': symbol, 'startTime': cursor,
            'endTime': min(end_ms - 1, cursor + 30 * 24 * 60 * 60 * 1000), 'limit': 1000,
        })
        if not page:
            break
        for row in page:
            stamp = int(row['fundingTime'])
            if start_ms <= stamp < end_ms:
                rows[stamp] = row
        next_cursor = int(page[-1]['fundingTime']) + 1
        if next_cursor <= cursor:
            raise RuntimeError(f'Funding pagination did not advance for {symbol}')
        cursor = next_cursor
        time.sleep(0.08)
    return [rows[key] for key in sorted(rows)]


def iso_ms(value: int) -> str:
    return datetime.fromtimestamp(value / 1000, timezone.utc).isoformat().replace('+00:00', 'Z')


def write_csv(path: Path, fieldnames: list[str], rows) -> int:
    count = 0
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
            count += 1
    return count


def export(config_path: Path, out_dir: Path, years: float, one_minute_days: int, five_minute_days: int,
           include_intrabar: bool, symbols_arg: str | None) -> Path:
    config = read_coin_config(config_path)
    coins = [value.strip().upper() for value in symbols_arg.split(',')] if symbols_arg else sorted(config)
    coins = list(dict.fromkeys(coins))
    unknown = [coin for coin in coins if coin not in config]
    if unknown:
        raise ValueError(f'Symbols are not present in COIN_CONFIG: {", ".join(unknown)}')
    exchange = get_exchange_symbols()
    out_dir.mkdir(parents=True, exist_ok=True)
    start = datetime.now(timezone.utc) - timedelta(days=365.2425 * years)
    now = datetime.now(timezone.utc)
    candle_fields = ['coin', 'symbol', 'interval', 'open_time_utc', 'open_time_ms', 'close_time_utc',
                     'open', 'high', 'low', 'close', 'volume', 'quote_volume', 'trade_count',
                     'taker_buy_base_volume', 'taker_buy_quote_volume']
    funding_fields = ['coin', 'symbol', 'funding_time_utc', 'funding_time_ms', 'funding_rate', 'mark_price', 'rate_type']
    candle_path, funding_path = out_dir / 'candles.csv', out_dir / 'funding_rates.csv'
    candle_count = 0
    coverage = []
    with candle_path.open('w', newline='', encoding='utf-8') as candle_handle, funding_path.open('w', newline='', encoding='utf-8') as funding_handle:
        candle_writer = csv.DictWriter(candle_handle, fieldnames=candle_fields)
        funding_writer = csv.DictWriter(funding_handle, fieldnames=funding_fields)
        candle_writer.writeheader(); funding_writer.writeheader()
        for coin in coins:
            symbol = f'{coin}USDT'
            meta = exchange.get(symbol, {})
            print(f'Fetching {symbol} ...', flush=True)
            interval_windows = [('1h', start), ('4h', start)]
            if include_intrabar:
                interval_windows.extend([
                    ('5m', now - timedelta(days=five_minute_days)),
                    ('1m', now - timedelta(days=one_minute_days)),
                ])
            for interval, window_start in interval_windows:
                lo, hi = utc_ms(window_start), utc_ms(now)
                effective_lo = max(lo, int(meta.get('onboardDate') or lo))
                rows = fetch_klines(symbol, interval, effective_lo, hi)
                for row in rows:
                    candle_writer.writerow({
                        'coin': coin, 'symbol': symbol, 'interval': interval,
                        'open_time_utc': iso_ms(int(row[0])), 'open_time_ms': int(row[0]),
                        'close_time_utc': iso_ms(int(row[6])), 'open': row[1], 'high': row[2],
                        'low': row[3], 'close': row[4], 'volume': row[5], 'quote_volume': row[7],
                        'trade_count': row[8], 'taker_buy_base_volume': row[9],
                        'taker_buy_quote_volume': row[10],
                    })
                candle_count += len(rows)
                coverage.append({'coin': coin, 'symbol': symbol, 'interval': interval,
                                 'rows': len(rows), 'first_utc': iso_ms(int(rows[0][0])),
                                 'last_utc': iso_ms(int(rows[-1][0])),
                                 'requested_start_utc': iso_ms(effective_lo),
                                 'exchange_current_status': meta.get('status', 'NOT_CURRENTLY_LISTED')})
            funding_rows = fetch_funding(symbol, utc_ms(start), utc_ms(now))
            for row in funding_rows:
                funding_writer.writerow({
                    'coin': coin, 'symbol': symbol,
                    'funding_time_utc': iso_ms(int(row['fundingTime'])),
                    'funding_time_ms': int(row['fundingTime']), 'funding_rate': row['fundingRate'],
                    'mark_price': row.get('markPrice', ''), 'rate_type': row.get('rateType', ''),
                })
            coverage[-1]['funding_rows'] = len(funding_rows)

    config_rows = []
    for coin in coins:
        for key, value in config[coin].items():
            config_rows.append({'coin': coin, 'config_key': key,
                                'config_value': json.dumps(value, sort_keys=True, separators=(',', ':'))})
    config_path_out = out_dir / 'percoin_config.csv'
    write_csv(config_path_out, ['coin', 'config_key', 'config_value'], config_rows)

    symbol_rows = []
    for coin in coins:
        symbol = f'{coin}USDT'
        row = exchange.get(symbol, {})
        symbol_rows.append({
            'coin': coin, 'symbol': symbol, 'currently_listed': bool(row),
            'status': row.get('status', ''), 'contract_type': row.get('contractType', ''),
            'base_asset': row.get('baseAsset', ''), 'quote_asset': row.get('quoteAsset', ''),
            'margin_asset': row.get('marginAsset', ''), 'onboard_date_ms': row.get('onboardDate', ''),
            'delivery_date_ms': row.get('deliveryDate', ''),
        })
    write_csv(out_dir / 'exchange_symbols.csv',
              ['coin', 'symbol', 'currently_listed', 'status', 'contract_type', 'base_asset',
               'quote_asset', 'margin_asset', 'onboard_date_ms', 'delivery_date_ms'], symbol_rows)

    manifest = {
        'source': 'Binance USDⓈ-M public market-data REST API',
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'config_source': config_path.name,
        'requested_history_start_utc': start.isoformat(),
        'requested_history_end_utc': now.isoformat(),
        'symbols': coins,
        'intrabar_included': include_intrabar,
        'intrabar_windows_days': {'5m': five_minute_days, '1m': one_minute_days} if include_intrabar else None,
        'candle_rows': candle_count,
        'coverage': coverage,
        'caveat': 'Public exchange data validates market-data calculations; it is not the engine signal/event log or account fill history.',
    }
    (out_dir / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    archive = out_dir / 'binance_validation_data.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for name in ('candles.csv', 'funding_rates.csv', 'percoin_config.csv', 'exchange_symbols.csv', 'manifest.json'):
            zf.write(out_dir / name, arcname=name)
    print(f'Wrote {candle_count:,} candles for {len(coins)} configured coins to {archive}', flush=True)
    return archive


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path('/engine/config.py'), help='Engine config.py mounted read-only')
    parser.add_argument('--out', type=Path, default=Path('/output'), help='Output directory')
    parser.add_argument('--years', type=float, default=2.0, help='History for 1h/4h candles and funding (default: 2)')
    parser.add_argument('--include-intrabar', action='store_true', help='Also download 5m and 1m candles for short windows')
    parser.add_argument('--five-minute-days', type=int, default=180)
    parser.add_argument('--one-minute-days', type=int, default=30)
    parser.add_argument('--symbols', help='Optional comma-separated subset of coin keys in COIN_CONFIG')
    args = parser.parse_args()
    if args.years <= 0 or args.years > 10:
        parser.error('--years must be greater than 0 and no more than 10')
    if args.five_minute_days < 1 or args.one_minute_days < 1:
        parser.error('Intrabar day windows must be positive')
    export(args.config, args.out, args.years, args.one_minute_days, args.five_minute_days,
           args.include_intrabar, args.symbols)


if __name__ == '__main__':
    main()
