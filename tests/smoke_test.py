"""Smoke test for the sample solve.

Runs solver.py against the committed sample data and checks that it finds an
OPTIMAL schedule and writes the output files. Stdlib only, so CI needs no test
framework:

    python tests/smoke_test.py

The assertions are pytest-compatible too, if you happen to have pytest:

    pytest tests/
"""

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUTPUTS = (
    REPO / "output" / "sample_schedule.csv",
    REPO / "output" / "sample_schedule.html",
)


def test_sample_solve_is_optimal_and_writes_output():
    result = subprocess.run(
        [sys.executable, "solver.py"],
        cwd=REPO,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, (
        f"solver.py exited with {result.returncode}.\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    assert "Status: OPTIMAL" in result.stdout, (
        f"expected the sample solve to report OPTIMAL.\n--- stdout ---\n{result.stdout}"
    )
    for path in OUTPUTS:
        assert path.exists(), f"solver.py did not write {path.relative_to(REPO)}"
        assert path.stat().st_size > 0, f"{path.relative_to(REPO)} is empty"


if __name__ == "__main__":
    test_sample_solve_is_optimal_and_writes_output()
    print("ok - sample solve is OPTIMAL and wrote output/sample_schedule.{csv,html}")
