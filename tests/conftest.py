"""Tests use a disposable database and never start the trading scheduler."""
import os
import tempfile
_test_storage=tempfile.TemporaryDirectory(prefix="signal-engine-tests-")
os.environ["SIGNAL_ENGINE_DB_PATH"]=_test_storage.name+"/signals.db"
os.environ["ENGINE_ENABLED"]="false"
os.environ["ENV"]="development"
os.environ["TRADING_MODE"]="paper"
