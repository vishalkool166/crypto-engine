#!/usr/bin/env python3
"""Ensure supported Python environment lookups have a safe template entry."""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / ".env.example"
ENV_NAME = re.compile(r"^([A-Z][A-Z0-9_]*)=")

# Runtime-managed, test-only, live-order or intentionally unsupported legacy values.
INTENTIONALLY_OMITTED = {
    "DASHBOARD_API_KEY",            # generated on first run
    "GITHUB_CLIENT_ID",             # legacy config only; no supported login flow
    "GITHUB_CLIENT_SECRET",         # legacy config only; no supported login flow
    "PYTEST_CURRENT_TEST",          # supplied by pytest
    "RECOVERY_CODES",               # generated and persisted by the application
    "SIGNAL_ENGINE_ALLOW_LIVE_TRADING",  # dangerous real-order override
    "SIGNAL_ENGINE_DB_PATH",        # test-only order-journal path override
}


def env_lookup_names(source: str) -> set[str]:
    tree = ast.parse(source)
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        is_getenv = (
            isinstance(func, ast.Attribute)
            and func.attr == "getenv"
            and isinstance(func.value, ast.Name)
            and func.value.id == "os"
        )
        is_environ_get = (
            isinstance(func, ast.Attribute)
            and func.attr == "get"
            and isinstance(func.value, ast.Attribute)
            and func.value.attr == "environ"
            and isinstance(func.value.value, ast.Name)
            and func.value.value.id == "os"
        )
        if (is_getenv or is_environ_get) and node.args:
            key = node.args[0]
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                found.add(key.value)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Subscript):
            continue
        value = node.value
        if (
            isinstance(node.ctx, ast.Load)
            and
            isinstance(value, ast.Attribute)
            and value.attr == "environ"
            and isinstance(value.value, ast.Name)
            and value.value.id == "os"
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, str)
        ):
            found.add(node.slice.value)
    return found


def main() -> int:
    if not TEMPLATE.is_file():
        raise SystemExit("Missing root .env.example")
    declared = {
        match.group(1)
        for line in TEMPLATE.read_text(encoding="utf-8").splitlines()
        if (match := ENV_NAME.match(line.strip()))
    }
    used: set[str] = set()
    for path in ROOT.rglob("*.py"):
        if any(part in {".venv", "venv", "node_modules", "__pycache__"} for part in path.parts):
            continue
        used |= env_lookup_names(path.read_text(encoding="utf-8"))
    missing = sorted(used - declared - INTENTIONALLY_OMITTED)
    if missing:
        print("Environment variables used in Python but absent from .env.example:")
        print("\n".join(f"- {name}" for name in missing))
        return 1
    print(
        f"Environment template passed: {len(declared)} keys; "
        f"{len(used)} source lookups; {len(INTENTIONALLY_OMITTED)} documented omissions."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
