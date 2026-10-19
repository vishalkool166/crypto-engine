"""Data recovery drills on synthetic SQLite records; no production DB access."""
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from backup_sqlite import backup
from restore_sqlite import restore


def make_backup(tmp_path):
    source = tmp_path / 'source.sqlite'
    with sqlite3.connect(source) as db:
        db.execute('CREATE TABLE intents (id INTEGER PRIMARY KEY, status TEXT NOT NULL)')
        db.execute('INSERT INTO intents (id,status) VALUES (1, ?)', ('uncertain',))
    archive = tmp_path / 'archive.sqlite'
    backup(source, archive)
    return source, archive


def test_restoration_preserves_data_and_never_overwrites(tmp_path):
    source, archive = make_backup(tmp_path)
    target = tmp_path / 'recovered.sqlite'
    digest = restore(archive, target)
    assert len(digest) == 64
    with sqlite3.connect(target) as db:
        assert db.execute('SELECT status FROM intents WHERE id=1').fetchone()[0] == 'uncertain'
    with pytest.raises(FileExistsError):
        restore(archive, target)
    with pytest.raises(FileExistsError):
        restore(archive, archive)
    assert source.is_file()


def test_tampered_backup_rejected_before_destination_creation(tmp_path):
    _, archive = make_backup(tmp_path)
    with sqlite3.connect(archive) as db:
        db.execute("UPDATE intents SET status = 'fake'")
    output = tmp_path / 'invalid.sqlite'
    with pytest.raises(ValueError, match='checksum mismatch'):
        restore(archive, output)
    assert not output.exists()


def test_missing_checksum_fails_closed(tmp_path):
    _, archive = make_backup(tmp_path)
    archive.with_suffix('.sqlite.sha256').unlink()
    with pytest.raises(FileNotFoundError):
        restore(archive, tmp_path / 'missing-hash.sqlite')
