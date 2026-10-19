"""Validate source-controlled engineering task ledger identity/dependencies/status."""
import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / 'docs/engineering/MASTER_TASK_LEDGER.csv'
JSON = ROOT / 'docs/engineering/MASTER_TASK_LEDGER.json'


def check() -> dict:
    with CSV.open(encoding='utf-8-sig', newline='') as file:
        rows = list(csv.DictReader(file))
    machine = json.loads(JSON.read_text())
    if rows != machine:
        raise AssertionError('CSV and JSON ledgers diverge')
    ids = [row['ID'] for row in rows]
    if len(ids) != len(set(ids)) or not rows:
        raise AssertionError('Task IDs are empty or duplicated')
    graph = {}
    for row in rows:
        deps = [] if row['Dependencies'] in ('', 'none') else row['Dependencies'].split(';')
        if any(dep not in ids for dep in deps):
            raise AssertionError(f"Unknown task dependency for {row['ID']}")
        graph[row['ID']] = deps
        if row['Status'] not in {'VERIFIED', 'IMPLEMENTED_UNVERIFIED', 'PLANNED', 'BLOCKED'}:
            raise AssertionError(f"Invalid status for {row['ID']}")
        if row['Status'] == 'VERIFIED' and not row['Evidence'].strip():
            raise AssertionError(f"Verified task missing evidence: {row['ID']}")
    visited, active = set(), set()
    def visit(task):
        if task in active:
            raise AssertionError('Cyclic task dependencies')
        if task in visited:
            return
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
