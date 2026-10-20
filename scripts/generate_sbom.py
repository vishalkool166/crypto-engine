"""Create a deterministic CycloneDX inventory from Python and npm manifests."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'docs/engineering/SBOM.cdx.json'
MANIFESTS = ('requirements.txt', 'requirements-test.txt', 'dashboard/package.json', 'dashboard/package-lock.json')


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _python_components() -> list[dict]:
    collected = {}
    for manifest, scope in (('requirements.txt', 'runtime'), ('requirements-test.txt', 'test')):
        for raw in (ROOT / manifest).read_text(encoding='utf-8').splitlines():
            line = raw.split('#', 1)[0].strip()
            if not line or line.startswith(('-', 'git+', 'http:')):
                continue
            match = re.match(r'^([A-Za-z0-9_.-]+)(?:\[[^]]+\])?\s*(.*)$', line)
            if not match:
                raise ValueError(f'Unparsed Python requirement line in {manifest}: {line}')
            name, constraint = match.groups()
            normalized = re.sub(r'[-_.]+', '-', name).lower()
            exact = re.fullmatch(r'==\s*([A-Za-z0-9_.+-]+)', constraint.strip())
            purl = f'pkg:pypi/{normalized}' + (f'@{exact.group(1)}' if exact else '')
            component = collected.setdefault(purl, {
                'type': 'library', 'name': name, 'purl': purl, '_scopes': set(),
                '_constraints': set(),
            })
            component['_scopes'].add(scope)
            component['_constraints'].add(constraint.strip() or 'unconstrained')
            if exact:
                component['version'] = exact.group(1)
    components = []
    for component in collected.values():
        scopes = sorted(component.pop('_scopes'))
        constraints = sorted(component.pop('_constraints'))
        component['properties'] = [
            {'name': 'signal-engine:dependency-scope', 'value': ','.join(scopes)},
            {'name': 'signal-engine:declared-constraint', 'value': ', '.join(constraints)},
        ]
        components.append(component)
    return components


def _npm_components() -> list[dict]:
    lock = json.loads((ROOT / 'dashboard/package-lock.json').read_text(encoding='utf-8'))
    manifest = json.loads((ROOT / 'dashboard/package.json').read_text(encoding='utf-8'))
    direct = set(manifest.get('dependencies', {})) | set(manifest.get('devDependencies', {}))
    direct_dev = set(manifest.get('devDependencies', {}))
    components = []
    for install_path, entry in sorted(lock.get('packages', {}).items()):
        if not install_path or not entry.get('version'):
            continue
        marker = 'node_modules/'
        if marker not in install_path:
            continue
        name = install_path.rsplit(marker, 1)[1]
        if not name:
            continue
        encoded_name = name.replace('@', '%40', 1) if name.startswith('@') else name
        component = {
            'type': 'library', 'name': name, 'version': str(entry['version']),
            'purl': f"pkg:npm/{encoded_name}@{entry['version']}",
            'properties': [{'name': 'signal-engine:dependency-scope',
                            'value': 'direct' if name in direct else 'transitive'},
                           {'name': 'signal-engine:development-dependency',
                            'value': str(bool(entry.get('dev') or name in direct_dev)).lower()}],
        }
        integrity = entry.get('integrity')
        if integrity and integrity.startswith('sha512-'):
            component['hashes'] = [{'alg': 'SHA-512', 'content': integrity.removeprefix('sha512-')}]
        components.append(component)
    return components


def render() -> str:
    hashes = [
        {'name': f'source-manifest:{name}', 'value': _sha256(ROOT / name)}
        for name in MANIFESTS
    ]
    body = {
        'bomFormat': 'CycloneDX', 'specVersion': '1.5', 'version': 1,
        'metadata': {
            'component': {'type': 'application', 'name': 'Signal Engine', 'version': 'source-candidate'},
            'properties': hashes,
            'tools': {'components': [{'type': 'application', 'name': 'Signal Engine SBOM generator',
                                     'version': '1.0'}]},
        },
        'components': sorted(_python_components() + _npm_components(), key=lambda item: (item['purl'], item['name'])),
    }
    return json.dumps(body, indent=2, sort_keys=True) + '\n'


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='fail if checked-in SBOM is stale')
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    content = render()
    if args.check:
        if not args.output.exists() or args.output.read_text(encoding='utf-8') != content:
            print('SBOM missing or stale; run scripts/generate_sbom.py', file=sys.stderr)
            return 1
        print(f'SBOM check passed: {len(json.loads(content)["components"])} dependency components.')
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(content, encoding='utf-8')
    print(f'Wrote {args.output} ({len(json.loads(content)["components"])} components)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
