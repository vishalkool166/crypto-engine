#!/usr/bin/env python3
"""Online SQLite backup with integrity validation, including WAL contents."""

import argparse, sqlite3, os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

p = argparse.ArgumentParser()
p.add_argument("destination")
p.add_argument(
    "--source", default=os.getenv("SIGNAL_ENGINE_DB_PATH", "database/signals.db")
)
a = p.parse_args()
source = Path(a.source).resolve()
dest = Path(a.destination).resolve()
if not source.is_file():
    raise SystemExit("Source database does not exist")
if dest.exists() or dest == source:
    raise SystemExit("Destination must be a new file")
dest.parent.mkdir(parents=True, exist_ok=True)
with (
    sqlite3.connect("file:" + str(source) + "?mode=ro", uri=True) as src,
    sqlite3.connect(dest) as dst,
):
    src.backup(dst)
    if dst.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise SystemExit("Backup integrity failed")
os.chmod(dest, 0o600)
print("Verified backup:", dest)
