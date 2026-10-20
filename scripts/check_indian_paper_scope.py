"""Guard against direct Angel One order-placement SDK calls in Indian modules."""
import ast
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SCOPED_FILES = [ROOT / 'api/indian.py', *sorted((ROOT / 'engines/indian').glob('*.py'))]
ORDER_METHODS = {'placeOrder', 'placeOrderFullResponse', 'modifyOrder', 'cancelOrder', 'cancelAllOrder'}


def violations() -> list[str]:
    found = []
    for path in SCOPED_FILES:
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr in ORDER_METHODS:
                found.append(f'{path.relative_to(ROOT)}:{node.lineno}: direct {node.func.attr} call')
    return found


if __name__ == '__main__':
    issues = violations()
    if issues:
        print('Indian market paper/data-only scope violated:', *issues, sep='\n', file=sys.stderr)
        raise SystemExit(1)
    print(f'Indian paper/data-only scope passed: scanned {len(SCOPED_FILES)} source files; no direct order-placement SDK call.')
