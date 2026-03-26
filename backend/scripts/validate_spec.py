# Spec: TEST-STRATEGY-001
"""Spec Validator -- Validates Spec MD files for completeness.

Checks each Spec file against the SPEC_TEMPLATE.md requirements and
outputs pass/warn/fail for each check.

Usage:
    cd backend
    uv run python -m scripts.validate_spec docs/specs/services/AUDIT_LOG_SPEC.md
    uv run python -m scripts.validate_spec --all

Returns exit code 0 if all checks pass, 1 if any FAIL found.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

# Force UTF-8 stdout on Windows to avoid cp949/cp1252 encoding errors
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from scripts.spec_parser import (
    BACKEND_DIR,
    PROJECT_ROOT,
    Color,
    SpecMetadata,
    find_spec_files,
    get_all_known_spec_ids,
    parse_spec_file,
)

# ---------------------------------------------------------------------------
# Check Results
# ---------------------------------------------------------------------------

PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"


def _icon(status: str) -> str:
    if status == PASS:
        return f"{Color.GREEN}PASS{Color.RESET}"
    elif status == WARN:
        return f"{Color.YELLOW}WARN{Color.RESET}"
    else:
        return f"{Color.RED}FAIL{Color.RESET}"


def _check_line(status: str, label: str, detail: str = "") -> str:
    icon = _icon(status)
    detail_str = f" {Color.DIM}({detail}){Color.RESET}" if detail else ""
    return f"  [{icon}] {label}{detail_str}"


# ---------------------------------------------------------------------------
# Individual Checks
# ---------------------------------------------------------------------------

def check_spec_id(meta: SpecMetadata) -> tuple[str, str]:
    """Check 1: Spec ID exists and matches expected pattern."""
    if not meta.spec_id:
        return FAIL, "No Spec ID found"
    # Pattern: PREFIX-MODULE-NNN or PREFIX-NNN
    import re
    if re.match(r"^[A-Z][A-Z0-9]+-(?:[A-Z]+-)*\d{3}$", meta.spec_id):
        return PASS, meta.spec_id
    # Also accept patterns like FS-AI-010, DM-001, SVC-001, API-ERR-001
    if re.match(r"^[A-Z][A-Z0-9-]+$", meta.spec_id):
        return PASS, meta.spec_id
    return WARN, f"Unusual pattern: {meta.spec_id}"


def check_ac_section(meta: SpecMetadata) -> tuple[str, str]:
    """Check 2: AC section exists with at least 1 AC."""
    count = len(meta.acceptance_criteria)
    if count == 0:
        return FAIL, "No acceptance criteria found"
    return PASS, f"{count} ACs defined"


def check_api_endpoints(meta: SpecMetadata) -> tuple[str, str]:
    """Check 3: API endpoints defined (if backend spec)."""
    if not meta.file_path:
        return WARN, "No file path"

    content = meta.file_path.read_text(encoding="utf-8")

    # Determine if this is a backend-relevant spec
    is_backend = any(kw in content.lower() for kw in [
        "api", "endpoint", "method", "path", "backend",
        "fastapi", "router", "service",
    ])

    if not is_backend:
        return PASS, "Not a backend spec (skipped)"
    if meta.has_api_endpoints:
        return PASS, "API endpoints defined"
    return WARN, "Backend spec but no API endpoints table"


def check_schemas(meta: SpecMetadata) -> tuple[str, str]:
    """Check 4: Request/Response schemas defined (if API endpoints exist)."""
    if not meta.has_api_endpoints:
        return PASS, "No API endpoints (skipped)"
    if meta.has_schemas:
        return PASS, "Schemas defined"
    return WARN, "API endpoints exist but no Request/Response schemas"


def check_impl_files(meta: SpecMetadata) -> tuple[str, str]:
    """Check 5: Implementation file mapping section exists."""
    if meta.has_impl_files:
        return PASS, "Implementation mapping present"
    return WARN, "No implementation file mapping"


def check_dependencies(meta: SpecMetadata) -> tuple[str, str]:
    """Check 6: Dependencies listed and resolvable."""
    if not meta.dependencies:
        return PASS, "No dependencies (standalone)"

    known_ids = get_all_known_spec_ids()
    missing = [d for d in meta.dependencies if d not in known_ids]

    if missing:
        return WARN, f"Unresolved deps: {', '.join(missing)}"
    return PASS, f"{len(meta.dependencies)} deps, all resolved"


def check_status(meta: SpecMetadata) -> tuple[str, str]:
    """Check 7: Status is one of Draft/Approved/Implemented."""
    valid = {"Draft", "Approved", "Implemented"}
    if not meta.status:
        return FAIL, "No status field found"
    if meta.status in valid:
        return PASS, meta.status
    # Case-insensitive match
    for v in valid:
        if meta.status.lower() == v.lower():
            return PASS, v
    return FAIL, f"Invalid status: {meta.status}"


def check_code_blocks(meta: SpecMetadata) -> tuple[str, str]:
    """Check 8: At least 1 code block present."""
    if meta.has_code_blocks:
        return PASS, "Code blocks present"
    return WARN, "No code blocks found"


# ---------------------------------------------------------------------------
# Validation Runner
# ---------------------------------------------------------------------------

ALL_CHECKS = [
    ("Spec ID",          check_spec_id),
    ("AC Section",       check_ac_section),
    ("API Endpoints",    check_api_endpoints),
    ("Schemas",          check_schemas),
    ("Implementation",   check_impl_files),
    ("Dependencies",     check_dependencies),
    ("Status",           check_status),
    ("Code Examples",    check_code_blocks),
]


def validate_spec(path: Path) -> tuple[int, int, int]:
    """Validate a single spec file. Returns (pass_count, warn_count, fail_count)."""
    meta = parse_spec_file(path)
    rel_path = path.relative_to(PROJECT_ROOT) if path.is_relative_to(PROJECT_ROOT) else path

    spec_label = meta.spec_id or "UNKNOWN"
    print(f"\n{Color.BOLD}{Color.CYAN}{spec_label}{Color.RESET} {Color.DIM}{rel_path}{Color.RESET}")

    pass_count = warn_count = fail_count = 0

    for label, check_fn in ALL_CHECKS:
        status, detail = check_fn(meta)
        print(_check_line(status, label, detail))
        if status == PASS:
            pass_count += 1
        elif status == WARN:
            warn_count += 1
        else:
            fail_count += 1

    return pass_count, warn_count, fail_count


def validate_all() -> int:
    """Validate all spec files and return exit code."""
    spec_files = find_spec_files()

    print(f"{Color.BOLD}{Color.BLUE}")
    print("=" * 60)
    print("  Spec Validator -- Completeness Check")
    print("  SPEC_TEMPLATE.md compliance")
    print("=" * 60)
    print(Color.RESET)

    total_pass = total_warn = total_fail = 0
    total_specs = 0
    specs_with_fails = 0

    for path in spec_files:
        p, w, f = validate_spec(path)
        total_pass += p
        total_warn += w
        total_fail += f
        total_specs += 1
        if f > 0:
            specs_with_fails += 1

    # Summary
    print(f"\n{Color.BOLD}")
    print("=" * 60)
    total_checks = total_pass + total_warn + total_fail
    pass_pct = (total_pass / total_checks * 100) if total_checks else 0

    print(f"  Specs validated:  {total_specs}")
    print(f"  Total checks:     {total_checks}")
    print(f"  {Color.GREEN}PASS: {total_pass}{Color.RESET}{Color.BOLD}  "
          f"{Color.YELLOW}WARN: {total_warn}{Color.RESET}{Color.BOLD}  "
          f"{Color.RED}FAIL: {total_fail}{Color.RESET}{Color.BOLD}")
    print(f"  Pass rate:        {pass_pct:.0f}%")

    if specs_with_fails > 0:
        print(f"\n  {Color.RED}{specs_with_fails} spec(s) have FAIL checks.{Color.RESET}")
    else:
        print(f"\n  {Color.GREEN}All specs pass mandatory checks.{Color.RESET}")

    print(Color.RESET)

    return 1 if total_fail > 0 else 0


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main() -> None:
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print("Usage:")
        print("  uv run python -m scripts.validate_spec <spec_path>")
        print("  uv run python -m scripts.validate_spec --all")
        print()
        print("Options:")
        print("  --all        Validate all specs in docs/specs/")
        print("  <spec_path>  Path to a single spec .md file")
        sys.exit(0)

    if args[0] == "--all":
        exit_code = validate_all()
        sys.exit(exit_code)

    # Single file mode
    spec_path = Path(args[0])
    if not spec_path.is_absolute():
        # Try relative to project root
        candidate = PROJECT_ROOT / spec_path
        if candidate.exists():
            spec_path = candidate
        else:
            # Try relative to CWD
            spec_path = Path.cwd() / args[0]

    if not spec_path.exists():
        print(f"{Color.RED}File not found: {spec_path}{Color.RESET}")
        sys.exit(1)

    print(f"{Color.BOLD}{Color.BLUE}")
    print("=" * 60)
    print("  Spec Validator -- Single File")
    print("=" * 60)
    print(Color.RESET)

    p, w, f = validate_spec(spec_path)
    total = p + w + f

    print(f"\n  {Color.GREEN}PASS: {p}{Color.RESET}  "
          f"{Color.YELLOW}WARN: {w}{Color.RESET}  "
          f"{Color.RED}FAIL: {f}{Color.RESET}")

    sys.exit(1 if f > 0 else 0)


if __name__ == "__main__":
    main()
