#!/bin/bash
echo "Installing dependencies..."
pip install redis>=5.0.0 -q
echo "Starting Freqtrade..."
freqtrade trade \
  --config /freqtrade/user_data/config.json \
  --strategy SignalEngineStrategy