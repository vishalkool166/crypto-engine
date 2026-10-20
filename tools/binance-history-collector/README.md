# Binance historical data collector

This standalone container uses only public Binance USDⓈ-M market-data endpoints. It needs no API key, cannot read account data, and has no order-placement code. It reads `COIN_CONFIG` as a Python AST literal from the mounted engine `config.py` without importing the engine or secrets.

It exports the configured coin set (currently 18) into `candles.csv` (1h and 4h, default two years), `funding_rates.csv`, `percoin_config.csv`, `exchange_symbols.csv`, and `manifest.json`. The same files are bundled in `binance_validation_data.zip`. `--include-intrabar` adds 5m candles for 180 days and 1m candles for 30 days to help test stop/target sequencing. Any candle gap or failed symbol download stops the export instead of silently accepting incomplete history. Only completed candles are included.

From `~/crypto-engine` on the server:

```bash
mkdir -p tools/binance-history-collector data/binance_validation
# Copy collector.py, Dockerfile and README.md into tools/binance-history-collector/
docker build -t signal-engine-binance-history tools/binance-history-collector
docker run --rm \
  -v "$PWD:/engine:ro" \
  -v "$PWD/data/binance_validation:/output" \
  signal-engine-binance-history \
  --config /engine/config.py --out /output --years 2 --include-intrabar
```

The completed archive will be `data/binance_validation/binance_validation_data.zip`. Upload that ZIP here. It contains only public market data and the selected per-coin configuration snapshot. For a smaller first transfer, omit `--include-intrabar`; the config and 1h/4h history remain included.

The collector uses `https://fapi.binance.com/fapi/v1/klines`, `/fapi/v1/fundingRate`, and `/fapi/v1/exchangeInfo`. Binance documents these as the USDⓈ-M public market-data endpoints. The requested history is kept separate from account/order/fill history; the archive alone cannot validate actual engine signal outcomes or execution slippage.
