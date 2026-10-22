#!/usr/bin/env python3
"""Verify SHA256SUMS for an extracted Signal Engine source distribution."""
from __future__ import annotations

import hashlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "SHA256SUMS"


def main() -> int:
    if not MANIFEST.is_file():
        print("Missing SHA256SUMS", file=sys.stderr)
        return 2
    failures: list[str] = []
    entries = 0
    for number, line in enumerate(MANIFEST.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            digest, name = line.split("  ", 1)
        except ValueError:
            failures.append(f"Malformed manifest line {number}")
            continue
        path = ROOT / name
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            failures.append(f"Invalid SHA-256 digest on line {number}")
            continue
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(ROOT.resolve()):
            failures.append(f"Missing or unsafe path: {name}")
            continue
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            failures.append(f"Digest mismatch: {name}")
        entries += 1
    if failures:
        for item in failures:
            print(item, file=sys.stderr)
        return 1
    if entries == 0:
        print("Manifest has no entries", file=sys.stderr)
        return 2
    print(f"Verified {entries} source files against SHA256SUMS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
