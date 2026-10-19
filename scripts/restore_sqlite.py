"""Offline integrity-checked restore of a backup into a NEW file.

Run only while the application is stopped; it does not touch active databases,
associated WAL/SHM files, or replace existing destinations. Intended for
operator-controlled recovery exercises, not an automatic production restore.
"""
import argparse
import hashlib
import sqlite3
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def restore(backup: Path, destination: Path, checksum: Path | None = None) -> str:
    if not backup.is_file():
        raise FileNotFoundError(f'Backup missing: {backup}')
    if destination.exists() or destination.resolve() == backup.resolve():
        raise FileExistsError('Restore destination must be a new, separate file')
    checksum = checksum if checksum is not None else backup.with_suffix(backup.suffix + '.sha256')
    if not checksum.is_file():
        raise FileNotFoundError(f'Backup checksum missing: {checksum}')
    stored = checksum.read_text().strip().split()
    if len(stored) != 2 or stored[1] != backup.name or len(stored[0]) != 64:
        raise ValueError('Malformed checksum manifest')
    expected = stored[0].lower()
    if not all(ch in '0123456789abcdef' for ch in expected):
        raise ValueError('Malformed checksum digest')
    digest = sha256_file(backup)
    if digest != expected:
        raise ValueError('Backup checksum mismatch')
    # SQLite online backup API makes a consistent copy, never a file-by-file
    # overwrite. A failed restore deletes only the NEW destination.
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with sqlite3.connect(f'file:{backup.resolve()}?mode=ro', uri=True) as src:
            with sqlite3.connect(destination) as dst:
                src.backup(dst)
                result = dst.execute('PRAGMA integrity_check').fetchone()
                if not result or result[0] != 'ok':
                    raise ValueError(f'Failed restored DB integrity check: {result}')
        return sha256_file(destination)
    except Exception:
        destination.unlink(missing_ok=True)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--checksum', type=Path)
    args = parser.parse_args()
    print('Restored SHA256:', restore(args.backup, args.destination, args.checksum))
