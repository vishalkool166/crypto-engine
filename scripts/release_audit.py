"""Read-only release audit: report local proof separately from external gates.

Usage: python scripts/release_audit.py --output /tmp/signal-release-audit.json
This script CANNOT certify deployment, profitability, or live-order safety.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
EXTERNAL_GATES = {
    'frontend_clean_install_lint_typecheck_build': 'PASS locally on Node 24.19/npm 11.9; Cloudflare Pages deployment checks still required',
    'frontend_browser_mobile_and_permissions': 'BLOCKED: authorized browser/staging deployment needed',
    'fastapi_google_email_sessions_csrf': 'BLOCKED: full Python 3.11 stack and staging browser needed',
    'redis_lua_and_reconnect': 'BLOCKED: test Redis instance needed',
    'aws_rebuild_migrations_and_rollback': 'BLOCKED: controlled staging AWS image and restored state needed',
    'exchange_testnet_reconciliation': 'BLOCKED: authorized paper/testnet fault drill needed',
    'signal_oos_quality_and_forward_paper': 'BLOCKED: verified historical 18-coin data and paper-forward window needed',
}


def command_result(*args: str) -> dict:
    try:
        completed = subprocess.run(args, cwd=ROOT, capture_output=True,
                                   text=True, timeout=120, check=False)
        output = (completed.stdout + '\n' + completed.stderr).strip()
        return {'status': 'PASS' if completed.returncode == 0 else 'FAIL',
                'returncode': completed.returncode,
                'detail': output[-900:]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'status': 'BLOCKED', 'detail': str(exc)}


def inspect_tree(root: Path = ROOT) -> dict:
    forbidden = []
    for path in root.rglob('*'):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in {'.git', 'node_modules', '__pycache__', '.venv', '.pytest_cache', 'dist'} for part in rel.parts):
            # Compiled/cached artifacts should not be packaged; their presence in a
            # local developer checkout is normal and is handled by .gitignore.
            continue
        if path.name == '.env' or path.suffix in {'.db', '.sqlite', '.sqlite3', '.pem', '.p12'}:
            forbidden.append(str(rel))
    issues = []
    if (root / '.github/workflows').exists(): issues.append('GitHub Actions must be absent')
    if (root / 'frontend').exists(): issues.append('Legacy compiled frontend is present')
    if forbidden: issues.append(f'Unprotected runtime data in source tree: {forbidden[:6]}')
    if (root / 'docs/engineering/MASTER_TASK_LEDGER.json').exists():
        issues.append('Duplicate ledger mirror remains')
    return {'status': 'PASS' if not issues else 'FAIL', 'detail': issues or ['No packaging hazards detected']}


def paper_mode_gate(mode: str) -> dict:
    normalized = (mode or '').strip().lower()
    if normalized == 'paper':
        return {'status': 'PASS', 'detail': 'Configured mode is paper'}
    return {'status': 'FAIL', 'detail': f'Release audit blocks non-paper mode: {normalized or "unset"}'}


def evaluate(run_tests: bool = True, root: Path = ROOT) -> dict:
    try:
        from config import cfg
        configured_mode = cfg.TRADING_MODE
    except Exception as exc:
        configured_mode = ''
    tasks = {
        'paper_mode_release_gate': paper_mode_gate(configured_mode),
        'source_tree': inspect_tree(root),
        'monorepo_contract': command_result(sys.executable, 'scripts/check_monorepo_contract.py'),
        'source_hygiene': command_result(sys.executable, 'scripts/check_source_hygiene.py'),
        'ledger_integrity': command_result(sys.executable, 'scripts/check_task_ledger.py'),
        'strategy_s0_integrity': command_result(sys.executable, 'scripts/freeze_strategy_baseline.py', '--check'),
        'openapi_contract': command_result(sys.executable, 'scripts/check_openapi_contract.py'),
        'api_security_inventory': command_result(sys.executable, 'scripts/check_api_inventory.py'),
        'database_schema_inventory': command_result(sys.executable, 'scripts/check_database_schema.py'),
        'sbom_inventory': command_result(sys.executable, 'scripts/generate_sbom.py', '--check'),
        'indian_paper_scope': command_result(sys.executable, 'scripts/check_indian_paper_scope.py'),
    }
    if run_tests:
        tasks['python_tests'] = command_result(sys.executable, '-m', 'pytest', '-q', '-rs', '--disable-warnings')
        if tasks['python_tests']['status'] == 'PASS' and re.search(r'\b\d+ skipped\b', tasks['python_tests']['detail']):
            tasks['python_tests']['status'] = 'PARTIAL'
    return {
        'generated_utc': datetime.now(timezone.utc).isoformat(),
        'release_certified': False,
        'paper_trading_only': configured_mode == 'paper',
        'local_checks': tasks,
        'external_gates': EXTERNAL_GATES,
        'note': 'Source-level checks are not production, exchange, revenue, or strategy certification.',
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--without-tests', action='store_true')
    args = parser.parse_args()
    result = evaluate(run_tests=not args.without_tests)
    body = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(body, encoding='utf-8')
    else:
        print(body)
    return 1 if any(x['status'] == 'FAIL' for x in result['local_checks'].values()) else 0


if __name__ == '__main__':
    raise SystemExit(main())
