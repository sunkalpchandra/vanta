"""Diff two static-demo snapshots: which files appeared, vanished, or changed.

Catches silent regressions in the export surface before a Pages deploy:
    python scripts/export_snapshot.py --out /tmp/snap-a
    ... make changes ...
    python scripts/export_snapshot.py --out /tmp/snap-b
    python scripts/diff_snapshot.py /tmp/snap-a /tmp/snap-b
"""

import argparse
import sys
from pathlib import Path


def _files(root: Path) -> dict[str, int]:
    return {
        str(p.relative_to(root)): p.stat().st_size
        for p in root.rglob("*")
        if p.is_file() and (p.suffix in {".json", ".svg", ".xml", ".csv"})
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before")
    parser.add_argument("after")
    args = parser.parse_args()
    before = _files(Path(args.before))
    after = _files(Path(args.after))

    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    resized = sorted(
        name for name in set(before) & set(after) if before[name] != after[name]
    )
    for name in added:
        print(f"+ {name}")
    for name in removed:
        print(f"- {name}")
    for name in resized:
        print(f"~ {name} ({before[name]} -> {after[name]} bytes)")
    if removed:
        print(
            f"\nWARNING: {len(removed)} files vanished — static pages reading them fall back to empty.",
            file=sys.stderr,
        )
        return 1
    print(f"\n{len(added)} added, {len(resized)} changed, none removed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
