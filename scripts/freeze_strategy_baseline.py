"""Record or verify the exact research S0 strategy sources, without invoking the engine.

The manifest is for change detection, NOT evidence that the strategy is profitable.
To freeze the baseline, run:
    python scripts/freeze_strategy_baseline.py --write
For subsequent research releases:
    python scripts/freeze_strategy_baseline.py --check
Use --root in isolated tests only. Never overwrite the baseline to make a drift check pass.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = 'docs/engineering/STRATEGY_S0_SHA256.json'
# These files define the research-facing crypto signal and entry-risk pipeline.
# Changes to other settings (e.g. execution/rate limits) must be separately audited.
SOURCE_PATHS = (
    'agents/signal_agent.py',
    'agents/nodes/grade_node.py',
    'agents/nodes/regime_node.py',
    'agents/nodes/risk_node.py',
    'agents/nodes/sizing_node.py',
    'agents/nodes/trend_node.py',
    'engines/scoring/scorer.py',
    'engines/trend/direction.py',
    'engines/regime/detector.py',
    'engines/risk/calculator.py',
    'engines/sizing/adaptive.py',
    'engines/core/candles.py',
    'engines/core/indicators.py',
    'engines/core/risk.py',
    'config.py',
)


def calculate(root: Path) -> dict[str, str]:
    """Fail if any mandatory baseline file is absent; never accept partial lists."""
    return {rel: hashlib.sha256((root / rel).read_bytes()).hexdigest()
            for rel in SOURCE_PATHS}


def verify(root: Path, manifest: Path) -> tuple[bool, list[str]]:
    try:
        expected = json.loads(manifest.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        return False, [f'Manifest missing or invalid: {exc}']
    if not isinstance(expected, dict) or set(expected) != set(SOURCE_PATHS):
        return False, ['Manifest must list exactly the frozen strategy sources']
    actual = calculate(root)
    drift = [rel for rel in SOURCE_PATHS if actual[rel] != expected[rel]]
    return not drift, drift


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--check', action='store_true')
    group.add_argument('--write', action='store_true')
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--manifest', type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    manifest = args.manifest or root / MANIFEST
    if args.write:
        if manifest.exists():
            parser.error('Refusing to overwrite existing S0 manifest; baseline changes require review')
        data = calculate(root)
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        print(f'Frozen {len(data)} strategy sources. Research-only; no live approval.')
        return 0
    passed, errors = verify(root, manifest)
    if not passed:
        for error in errors:
            print('STRATEGY BASELINE DRIFT:', error)
        return 1
    print(f'Strategy S0 unchanged: {len(SOURCE_PATHS)} source hashes match.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
