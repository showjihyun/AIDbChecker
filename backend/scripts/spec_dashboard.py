# Spec: TEST-STRATEGY-001
"""Spec AC Coverage Dashboard -- Cross-references ACs with test results.

Parses ALL specs for ACs, runs pytest --collect-only to discover tests,
and shows overall coverage in a formatted dashboard.

Usage:
    cd backend
    uv run python -m scripts.spec_dashboard
"""

from __future__ import annotations

import io
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Force UTF-8 stdout on Windows to avoid cp949/cp1252 encoding errors
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from scripts.spec_parser import (
    BACKEND_DIR,
    TESTS_DIR,
    Color,
    SpecMetadata,
    ac_to_function_prefix,
    find_spec_refs_in_tests,
    parse_all_specs,
)

# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass
class ACStatus:
    spec_id: str
    ac_id: str
    description: str
    has_test: bool = False
    test_status: str = "none"  # "pass", "fail", "skip", "none"
    test_names: list[str] = field(default_factory=list)


@dataclass
class SpecCoverage:
    spec_id: str
    acs: list[ACStatus] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.acs)

    @property
    def passed(self) -> int:
        return sum(1 for ac in self.acs if ac.test_status == "pass")

    @property
    def skipped(self) -> int:
        return sum(1 for ac in self.acs if ac.test_status == "skip")

    @property
    def failed(self) -> int:
        return sum(1 for ac in self.acs if ac.test_status == "fail")

    @property
    def covered(self) -> int:
        return sum(1 for ac in self.acs if ac.has_test)

    @property
    def coverage_pct(self) -> float:
        if self.total == 0:
            return 0.0
        return (self.passed / self.total) * 100


# ---------------------------------------------------------------------------
# Test Discovery
# ---------------------------------------------------------------------------

def collect_test_results() -> dict[str, str]:
    """Run pytest -v and parse output to get per-test statuses.

    Returns a dict mapping test node IDs to status ("pass", "fail", "skip").
    """
    import re as _re

    results: dict[str, str] = {}

    # Run pytest in verbose mode to get PASSED/FAILED/SKIPPED per line
    try:
        proc = subprocess.run(
            [
                sys.executable, "-m", "pytest",
                "tests/", "-v", "--tb=no", "--no-header",
                "--override-ini=addopts=",
            ],
            capture_output=True,
            text=True,
            cwd=str(BACKEND_DIR),
            timeout=180,
        )

        # Parse lines like: tests/unit/test_auth.py::test_login PASSED
        pattern = _re.compile(r"^(\S+::\S+)\s+(PASSED|FAILED|SKIPPED|ERROR)")
        for line in proc.stdout.splitlines():
            match = pattern.match(line.strip())
            if match:
                nodeid = match.group(1)
                outcome = match.group(2)
                if outcome == "PASSED":
                    results[nodeid] = "pass"
                elif outcome in ("FAILED", "ERROR"):
                    results[nodeid] = "fail"
                elif outcome == "SKIPPED":
                    results[nodeid] = "skip"

    except (subprocess.TimeoutExpired, FileNotFoundError):
        # Fallback: run pytest --collect-only to just find test names
        try:
            proc = subprocess.run(
                [
                    sys.executable, "-m", "pytest",
                    "tests/", "--collect-only", "-q",
                    "--override-ini=addopts=",
                ],
                capture_output=True,
                text=True,
                cwd=str(BACKEND_DIR),
                timeout=60,
            )
            for line in proc.stdout.splitlines():
                line = line.strip()
                if "::" in line and not line.startswith(("=", "-", " ")):
                    results[line] = "skip"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    return results


def collect_test_functions_and_markers() -> tuple[set[str], dict[str, list[str]]]:
    """Collect test function names and spec_ref markers from test files.

    Returns:
        - set of all test function names
        - dict mapping "SPEC_ID:AC-N" -> list of test function names
    """
    import re

    all_funcs: set[str] = set()
    if not TESTS_DIR.exists():
        return all_funcs, {}

    for py_file in TESTS_DIR.rglob("*.py"):
        if py_file.name.startswith("__"):
            continue
        content = py_file.read_text(encoding="utf-8")
        for match in re.finditer(r"(?:def|async\s+def)\s+(test_\w+)", content):
            all_funcs.add(match.group(1))

    spec_refs = find_spec_refs_in_tests(TESTS_DIR)
    return all_funcs, spec_refs


# ---------------------------------------------------------------------------
# Coverage Computation
# ---------------------------------------------------------------------------

def compute_coverage(
    specs: list[SpecMetadata],
    test_funcs: set[str],
    spec_refs: dict[str, list[str]],
    test_results: dict[str, str],
) -> list[SpecCoverage]:
    """Cross-reference specs with test data to compute coverage."""
    coverages: list[SpecCoverage] = []

    # Build a map from function name to test result status
    func_status: dict[str, str] = {}
    for nodeid, status in test_results.items():
        # nodeid format: tests/unit/test_foo.py::test_bar
        if "::" in nodeid:
            func_name = nodeid.split("::")[-1]
            func_status[func_name] = status

    for spec in specs:
        if not spec.acceptance_criteria:
            continue

        cov = SpecCoverage(spec_id=spec.spec_id or "UNKNOWN")

        for ac in spec.acceptance_criteria:
            ac_status = ACStatus(
                spec_id=spec.spec_id or "UNKNOWN",
                ac_id=ac.ac_id,
                description=ac.description,
            )

            # Check by function name prefix
            prefix = ac_to_function_prefix(spec.spec_id or "", ac.ac_id)
            matching_funcs = [f for f in test_funcs if f.startswith(prefix)]

            # Check by spec_ref marker
            ref_key = f"{spec.spec_id}:{ac.ac_id}"
            ref_funcs = spec_refs.get(ref_key, [])

            all_matching = list(set(matching_funcs + ref_funcs))
            ac_status.test_names = all_matching
            ac_status.has_test = len(all_matching) > 0

            if all_matching:
                # Determine aggregated status
                statuses = []
                for func in all_matching:
                    if func in func_status:
                        statuses.append(func_status[func])
                    else:
                        statuses.append("skip")

                if any(s == "fail" for s in statuses):
                    ac_status.test_status = "fail"
                elif any(s == "pass" for s in statuses):
                    ac_status.test_status = "pass"
                else:
                    ac_status.test_status = "skip"
            else:
                ac_status.test_status = "none"

            cov.acs.append(ac_status)

        coverages.append(cov)

    return coverages


# ---------------------------------------------------------------------------
# Dashboard Output
# ---------------------------------------------------------------------------

def print_dashboard(coverages: list[SpecCoverage]) -> None:
    """Print the formatted coverage dashboard."""
    C = Color

    # Header
    print()
    print(f"{C.BOLD}{C.BLUE}")
    print("+" + "=" * 66 + "+")
    print("|" + "SPEC AC COVERAGE DASHBOARD".center(66) + "|")
    print("+" + "=" * 66 + "+")
    print(C.RESET)

    # Column headers
    header = (
        f"  {C.BOLD}{'Spec':<22} {'ACs':>4}  {'Pass':>4}  {'Skip':>4}  "
        f"{'Fail':>4}  {'Coverage':>10}{C.RESET}"
    )
    print(header)
    print(f"  {'-' * 62}")

    total_acs = 0
    total_pass = 0
    total_skip = 0
    total_fail = 0
    specs_complete = 0
    best_incomplete: SpecCoverage | None = None
    best_incomplete_pct = -1.0

    for cov in sorted(coverages, key=lambda c: c.spec_id):
        total_acs += cov.total
        total_pass += cov.passed
        total_skip += cov.skipped
        total_fail += cov.failed

        pct = cov.coverage_pct
        is_complete = cov.passed == cov.total and cov.total > 0

        if is_complete:
            specs_complete += 1
            pct_str = f"{C.GREEN}{pct:5.0f}% {C.RESET}"
        elif cov.failed > 0:
            pct_str = f"{C.RED}{pct:5.0f}% {C.RESET}"
        elif pct > 0:
            pct_str = f"{C.YELLOW}{pct:5.0f}% {C.RESET}"
        else:
            pct_str = f"{C.RED}{pct:5.0f}% {C.RESET}"

        # Track best incomplete spec for "next to implement" suggestion
        if not is_complete and pct > best_incomplete_pct:
            best_incomplete_pct = pct
            best_incomplete = cov

        pass_c = f"{C.GREEN}{cov.passed:4}{C.RESET}" if cov.passed > 0 else f"{cov.passed:4}"
        skip_c = f"{C.YELLOW}{cov.skipped:4}{C.RESET}" if cov.skipped > 0 else f"{cov.skipped:4}"
        fail_c = f"{C.RED}{cov.failed:4}{C.RESET}" if cov.failed > 0 else f"{cov.failed:4}"

        print(f"  {cov.spec_id:<22} {cov.total:4}  {pass_c}  {skip_c}  "
              f"{fail_c}  {pct_str}")

    # Summary
    total_cov_pct = (total_pass / total_acs * 100) if total_acs else 0
    total_specs = len(coverages)

    print(f"  {'-' * 62}")
    print(f"{C.BOLD}")

    total_pass_str = f"{C.GREEN}{total_pass}{C.RESET}{C.BOLD}"
    total_skip_str = f"{C.YELLOW}{total_skip}{C.RESET}{C.BOLD}"
    total_fail_str = f"{C.RED}{total_fail}{C.RESET}{C.BOLD}"

    print(f"  {'TOTAL':<22} {total_acs:4}  {total_pass_str:>14}  "
          f"{total_skip_str:>14}  {total_fail_str:>14}  "
          f"{total_cov_pct:5.0f}%")

    print(f"  Specs complete:     {specs_complete}/{total_specs} "
          f"({specs_complete / total_specs * 100:.0f}%)" if total_specs else "")

    if best_incomplete and best_incomplete.total > 0:
        remaining = best_incomplete.total - best_incomplete.passed
        print(f"  {C.CYAN}Next to implement:{C.RESET}{C.BOLD} "
              f"{best_incomplete.spec_id} "
              f"({best_incomplete.coverage_pct:.0f}%"
              f" -> {remaining} ACs left){C.RESET}")

    print(f"\n{C.BOLD}{C.BLUE}")
    print("+" + "=" * 66 + "+")
    print(C.RESET)


def print_detailed(coverages: list[SpecCoverage]) -> None:
    """Print detailed per-AC breakdown for specs with issues."""
    C = Color
    incomplete = [c for c in coverages if c.passed < c.total]

    if not incomplete:
        return

    print(f"\n{C.BOLD}Detailed AC Breakdown (incomplete specs):{C.RESET}\n")

    for cov in sorted(incomplete, key=lambda c: c.spec_id):
        print(f"  {C.BOLD}{C.CYAN}{cov.spec_id}{C.RESET}")
        for ac in cov.acs:
            if ac.test_status == "pass":
                icon = f"{C.GREEN}PASS{C.RESET}"
            elif ac.test_status == "fail":
                icon = f"{C.RED}FAIL{C.RESET}"
            elif ac.test_status == "skip":
                icon = f"{C.YELLOW}SKIP{C.RESET}"
            else:
                icon = f"{C.RED}NONE{C.RESET}"

            desc_short = ac.description[:50] + "..." if len(ac.description) > 50 else ac.description
            print(f"    [{icon}] {ac.ac_id}: {C.DIM}{desc_short}{C.RESET}")
        print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    C = Color

    print(f"{C.BOLD}{C.BLUE}")
    print("=" * 60)
    print("  Spec AC Coverage Dashboard")
    print("  TEST-STRATEGY-001")
    print("=" * 60)
    print(C.RESET)

    # Step 1: Parse all specs
    print(f"  {C.DIM}Parsing specs...{C.RESET}", end="", flush=True)
    specs = parse_all_specs()
    specs_with_acs = [s for s in specs if s.acceptance_criteria]
    print(f" {len(specs_with_acs)} specs with ACs (of {len(specs)} total)")

    # Step 2: Collect test functions and spec_ref markers
    print(f"  {C.DIM}Scanning tests...{C.RESET}", end="", flush=True)
    test_funcs, spec_refs = collect_test_functions_and_markers()
    print(f" {len(test_funcs)} test functions, {len(spec_refs)} spec refs")

    # Step 3: Collect test results (run pytest or read cache)
    print(f"  {C.DIM}Collecting test results...{C.RESET}", end="", flush=True)
    test_results = collect_test_results()
    print(f" {len(test_results)} results")

    # Step 4: Compute coverage
    coverages = compute_coverage(specs_with_acs, test_funcs, spec_refs, test_results)

    # Step 5: Display
    print_dashboard(coverages)

    # Step 6: Show detailed breakdown for incomplete specs
    show_detail = "--detail" in sys.argv or "-d" in sys.argv
    if show_detail:
        print_detailed(coverages)


if __name__ == "__main__":
    main()
