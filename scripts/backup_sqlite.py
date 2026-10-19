"""Transactional one-off SQLite backup. Never modifies the source database."""
import argparse
import hashlib
import sqlite3
from pathlib import Path


def backup(source: Path, destination: Path) -> str:
    if not source.is_file():
        raise FileNotFoundError(f'Source database missing: {source}')
    if destination.exists():
        raise FileExistsError(f'Refusing to overwrite: {destination}')
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with sqlite3.connect(f'file:{source.resolve()}?mode=ro', uri=True) as src:
            with sqlite3.connect(destination) as dst:
                src.backup(dst)
                result = dst.execute('PRAGMA integrity_check').fetchone()[0]
                if result != 'ok':
                    raise RuntimeError(f'SQLite integrity check failed: {result}')
        digest = hashlib.sha256(destination.read_bytes()).hexdigest()
        destination.with_suffix(destination.suffix+'.sha256').write_text(f'{digest}  {destination.name}\n')
        return digest
    except Exception:
        destination.unlink(missing_ok=True)
        raise

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--destination', type=Path, required=True)
    args = p.parse_args()
    print('SHA256:', backup(args.source, args.destination))
