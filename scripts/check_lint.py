"""Reject new Ruff findings without hiding the reviewed legacy backlog."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "scripts" / "lint_baseline.json"
CLEAN_PATHS = {
    "brighteyes_mcs/ui/controllers/statistics.py",
    "scripts/check_docs.py", "scripts/check_lint.py",
    "test/test_statistics.py", "test/test_quality_checks.py",
}


def findings() -> Counter:
    result = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "brighteyes_mcs", "scripts", "test",
         "--output-format=json"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False,
    )
    if result.returncode not in (0, 1):
        raise RuntimeError(result.stderr or "Ruff failed")
    counts: Counter = Counter()
    for item in json.loads(result.stdout):
        path = Path(item["filename"])
        source = path.read_text(encoding="utf-8-sig").splitlines()
        # Line numbers shift during cleanup; source, diagnostic and count stay useful.
        key = (
            path.relative_to(ROOT).as_posix(), item["code"], item["message"],
            source[item["location"]["row"] - 1].strip(),
        )
        counts[key] += 1
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-baseline", action="store_true")
    args = parser.parse_args()
    current = findings()
    clean_failures = {key: count for key, count in current.items() if key[0] in CLEAN_PATHS}
    if clean_failures:
        for key, count in clean_failures.items():
            print(f"Clean module violation ({count}): {' | '.join(key)}")
        return 1
    if args.write_baseline:
        BASELINE.write_text(
            json.dumps([{"key": list(key), "count": count}
                        for key, count in sorted(current.items())], indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Recorded {sum(current.values())} legacy findings; review the baseline diff.")
        return 0
    baseline = Counter({tuple(row["key"]): row["count"]
                        for row in json.loads(BASELINE.read_text(encoding="utf-8"))})
    new = current - baseline
    for key, count in sorted(new.items()):
        print(f"New lint finding ({count}): {' | '.join(key)}")
    print(f"Lint: {sum(new.values())} new, {sum(current.values())} existing findings")
    return int(bool(new))


if __name__ == "__main__":
    raise SystemExit(main())
