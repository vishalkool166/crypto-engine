"""Low-risk architecture regression guard. No network or broker access."""
from pathlib import Path
import hashlib
import json
import sys
ROOT=Path(__file__).resolve().parents[1]
REFERENCE=ROOT/'docs/engineering/UPSTREAM_RUNTIME_SHA256.json'
expected=json.loads(REFERENCE.read_text())
problems=[]
for path,digest in expected.items():
    file=ROOT/path
    if not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest()!=digest:
        problems.append(f'Existing AWS runtime file altered: {path}')
if (ROOT/'.github/workflows').exists(): problems.append('GitHub Actions workflow directory found')
for rel in ('main.py','config.py','scheduler.py','docker-compose.yml','Dockerfile','dashboard/package-lock.json','dashboard/src/index.css','dashboard/vite.config.ts','frontend/index.html'):
    if not (ROOT/rel).exists(): problems.append(f'Expected file missing: {rel}')
css=(ROOT/'dashboard/src/index.css').read_text()
for token in ("'Outfit'",'--background:             0 0% 100%;','--background:             0 0% 3.9%;'):
    if token not in css: problems.append(f'Original frontend styling changed: {token}')
vite=(ROOT/'dashboard/vite.config.ts').read_text()
if 'runtimeCaching: []' not in vite: problems.append('Service worker may cache authenticated APIs')
if 'dist' not in vite: problems.append('Dashboard not isolated to dist build output')
lock=(ROOT/'dashboard/package-lock.json').read_text()
if '.codeartifact.' in lock: problems.append('Private AWS npm registry URL remains in dashboard lockfile')
if problems:
    for p in problems: print('FAIL:',p,file=sys.stderr)
    raise SystemExit(1)
print('Monorepo contract passed (static checks only).')
