"""Exercise transactionally consistent backups on synthetic data only."""
import sqlite3
import sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from backup_sqlite import backup


def test_backup_snapshot_and_restore_integrity(tmp_path):
    src, dest = tmp_path/'journal.sqlite', tmp_path/'offsite'/'backup.sqlite'
    with sqlite3.connect(src) as db:
        db.execute('create table intents (order_id text primary key, status text not null)')
        db.execute('insert into intents values (?,?)', ('intent-1','uncertain'))
    digest = backup(src,dest)
    assert len(digest)==64
    with sqlite3.connect(dest) as db:
        assert db.execute('pragma integrity_check').fetchone()[0]=='ok'
        assert db.execute('select status from intents').fetchone()[0]=='uncertain'
    with pytest.raises(FileExistsError):
        backup(src,dest)


def test_missing_source_does_not_create_destination(tmp_path):
    dst=tmp_path/'dest.sqlite'
    with pytest.raises(FileNotFoundError):
        backup(tmp_path/'missing.sqlite',dst)
    assert not dst.exists()
