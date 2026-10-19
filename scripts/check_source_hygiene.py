"""Inspect tracked source-like files; intentionally excludes personal data and binaries."""
from pathlib import Path
import re
ROOT = Path(__file__).resolve().parents[1]
scan_dirs = [ROOT / 'agents', ROOT / 'api', ROOT / 'auth.py', ROOT / 'main.py', ROOT / 'trade', ROOT / 'saas', ROOT / 'dashboard' / 'src', ROOT / 'dashboard' / 'public', ROOT / 'scripts']
skip = {'node_modules', '.venv', '__pycache__', 'dist', '.pytest_cache', 'database', 'frontend'}
errors = []
for base in scan_dirs:
    for path in ([base] if base.is_file() else base.rglob('*')):
        if not path.is_file() or len(path.parts) > 100: continue
        if any(part in skip for part in path.relative_to(base if base.is_dir() else base.parent).parts[:-1]): continue
        if path.name in {'.env', '.env.production', 'credentials.json'}:
            errors.append(str(path.relative_to(ROOT))); continue
        if path.suffix not in {'.py', '.ts', '.tsx', '.json', '.yml', '.yaml', '.sh', '.md'}: continue
        try: data = path.read_text()
        except (UnicodeError, OSError): continue
        if re.search(r'\.codeartifact\.[a-z0-9-]+\.amazonaws\.com', data):
            errors.append(f'private registry in {path.relative_to(ROOT)}')
        if re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----', data):
            errors.append(f'private key in {path.relative_to(ROOT)}')
if errors:
    raise SystemExit('Repository hygiene failures:\n'+'\n'.join(errors))
print('Source hygiene scan passed (heuristic only; not a full secret scanner).')
