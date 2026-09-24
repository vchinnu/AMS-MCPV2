"""Run every offline test suite and report pass/fail.

    python test_suite/run_all.py

test_remote.py is excluded — it is an interactive client for the deployed
server, not an offline test.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent

SUITES = [
    "test_tools.py",            # schema registry, read-only guard, live LA queries
    "test_new_analyzers.py",    # NetWeaver analyzers + domain knowledge
    "test_pipeline.py",         # analyzer registry -> cache -> TOON -> get_details
    "test_cpu_attribution.py",  # CPU attribution domain functions
]


def main() -> int:
    # The suites print ✓/✗; force UTF-8 so they do not die on a cp1252 console.
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}

    results: list[tuple[str, bool, str]] = []
    for suite in SUITES:
        proc = subprocess.run(
            [sys.executable, str(HERE / suite)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        ok = proc.returncode == 0
        tail = (proc.stdout or "").strip().splitlines()
        detail = "" if ok else ((proc.stderr or "").strip().splitlines() or tail or [""])[-1]
        results.append((suite, ok, detail))
        print(f"{'PASS' if ok else 'FAIL'}  {suite}")
        if not ok:
            print(f"      {detail}")

    failed = [name for name, ok, _ in results if not ok]
    print()
    print(f"{len(results) - len(failed)}/{len(results)} suites passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
