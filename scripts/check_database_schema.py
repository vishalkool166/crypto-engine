"""Generate/check a safe source-level inventory of SQLAlchemy table metadata."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'docs/engineering/DATABASE_SCHEMA_INVENTORY.md'
CHILD = r'''
import json
import database
tables = []
for name, table in sorted(database.Base.metadata.tables.items()):
    columns = []
    for column in table.columns:
        foreign_keys = sorted(f"{fk.column.table.name}.{fk.column.name}" for fk in column.foreign_keys)
        columns.append({
            "name": column.name,
            "type": str(column.type),
            "nullable": column.nullable,
            "primary_key": column.primary_key,
            "foreign_keys": foreign_keys,
        })
    tables.append({"name": name, "columns": columns})
print(json.dumps(tables, sort_keys=True))
'''


def render() -> str:
    with tempfile.TemporaryDirectory(prefix='signal-schema-') as temp:
        env = os.environ.copy()
        env['SIGNAL_ENGINE_DATABASE_PATH'] = str(Path(temp) / 'schema-only.sqlite')
        result = subprocess.run([sys.executable, '-c', CHILD], cwd=ROOT, env=env,
                                check=True, capture_output=True, text=True)
    tables = json.loads(result.stdout)
    lines = [
        '# Database schema inventory',
        '',
        '> Generated from SQLAlchemy model metadata by `scripts/check_database_schema.py`. This describes the source models, not a live database or a migration history. The deployed schema must be inspected from a sanitized copy before any migration.',
        '',
        f"Source tables: **{len(tables)}**. Columns include declared type, nullability, primary-key flag, and foreign-key target.",
        '',
        '| Table | Columns |',
        '|---|---|',
    ]
    for table in tables:
        columns = []
        for column in table['columns']:
            label = f"`{column['name']}` {column['type']}"
            if column['primary_key']:
                label += ' PK'
            if not column['nullable']:
                label += ' NOT NULL'
            if column['foreign_keys']:
                label += ' → ' + ', '.join(f"`{target}`" for target in column['foreign_keys'])
            columns.append(label)
        lines.append(f"| `{table['name']}` | {'; '.join(columns)} |")
    lines += [
        '',
        '## Migration boundary',
        '',
        'The application currently has model metadata and startup table creation, but this inventory is not a reversible migration system. Before deployment changes, compare this inventory with a backup copy of the active database, preserve unknown columns/data, and rehearse forward migration and rollback. Never run a schema reset against production data.',
        '',
    ]
    return '\n'.join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true', help='write the generated inventory')
    args = parser.parse_args()
    expected = render()
    if args.write:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(expected, encoding='utf-8')
        print(f'Wrote {OUTPUT.relative_to(ROOT)}')
        return 0
    if not OUTPUT.exists() or OUTPUT.read_text(encoding='utf-8') != expected:
        print('Database schema inventory is missing or stale; run scripts/check_database_schema.py --write', file=sys.stderr)
        return 1
    count_line = next(line for line in expected.splitlines() if line.startswith('Source tables:'))
    count = count_line.split('**')[1]
    print(f'Database schema inventory passed: {count} source tables classified.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
