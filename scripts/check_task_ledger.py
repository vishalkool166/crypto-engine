"""Validate the canonical CSV engineering ledger: IDs, dependencies, and evidence.

There is deliberately one source of truth. Consumers can parse CSV directly; no
second JSON file is maintained or allowed to drift silently.
"""
import csv
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / 'docs/engineering/MASTER_TASK_LEDGER.csv'
REQUIRED_FIELDS = {'ID', 'Dependencies', 'Status', 'Evidence', 'Title', 'Acceptance'}
STATES = {'VERIFIED', 'IMPLEMENTED_UNVERIFIED', 'PLANNED', 'BLOCKED'}


def check(path: Path = LEDGER) -> dict:
    with path.open(encoding='utf-8-sig', newline='') as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames or not REQUIRED_FIELDS.issubset(reader.fieldnames):
            raise AssertionError('Ledger missing required columns')
        rows = list(reader)
    ids = [row['ID'] for row in rows]
    if not rows or any(not identifier for identifier in ids) or len(ids) != len(set(ids)):
        raise AssertionError('Task IDs are empty or duplicated')
    valid_ids = set(ids)
    graph = {}
    for row in rows:
        deps = [] if row['Dependencies'] in ('', 'none') else row['Dependencies'].split(';')
        if any(dep not in valid_ids for dep in deps):
            raise AssertionError(f"Unknown task dependency for {row['ID']}")
        graph[row['ID']] = deps
        if row['Status'] not in STATES:
            raise AssertionError(f"Invalid status for {row['ID']}")
        if row['Status'] == 'VERIFIED' and not row['Evidence'].strip():
            raise AssertionError(f"Verified task missing evidence: {row['ID']}")
    visited, active = set(), set()

    def visit(task):
        if task in active:
            raise AssertionError('Cyclic task dependencies')
        if task not in visited:
            active.add(task)
            for dep in graph[task]:
                visit(dep)
            active.remove(task)
            visited.add(task)

    for task in graph:
        visit(task)
    return dict(Counter(row['Status'] for row in rows))


if __name__ == '__main__':
    print('Task ledger integrity passed:', check())
