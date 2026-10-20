#!/usr/bin/env bash
# Manual reproducible verification. Does not start the scheduler or contact exchanges.
set -euo pipefail
cd "$(dirname "$0")/.."
python -m compileall -q -x '(^\./frontend/|^\./dashboard/)' .
python scripts/check_monorepo_contract.py
python scripts/check_source_hygiene.py
python scripts/check_env_template.py
python scripts/check_task_ledger.py
python scripts/check_openapi_contract.py
python scripts/check_api_inventory.py
python scripts/check_database_schema.py
python scripts/generate_sbom.py --check
python scripts/check_indian_paper_scope.py
python scripts/freeze_strategy_baseline.py --check
PYTHONPATH=. python -m pytest -q -rs --disable-warnings
if [[ "${CHECK_FRONTEND:-0}" == "1" ]]; then
  cd dashboard
  npm ci --no-audit --no-fund
  npm run lint
  npx tsc -b
  npm run build
else
  echo 'Frontend build not run. Re-run with CHECK_FRONTEND=1 once npm registry is reachable.'
fi
