# Spec: TEST-STRATEGY-001
"""Spec-Driven Test Stub Generator.

Reads all Spec MD files from docs/specs/, parses Acceptance Criteria sections,
and generates pytest test stubs for any AC that lacks a corresponding test.

Usage:
    cd backend
    uv run python -m scripts.gen_spec_tests

Rules:
- Idempotent: safe to run multiple times without overwriting existing tests
- Only generates stubs for missing ACs
- Preserves all existing test code
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Project root is two levels up from this script (backend/scripts/ -> backend/ -> project/)
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent
SPECS_DIR = PROJECT_ROOT / "docs" / "specs"
TESTS_UNIT_DIR = BACKEND_DIR / "tests" / "unit"

# Patterns for parsing spec files
SPEC_ID_PATTERN = re.compile(
    r"\*\*Spec ID\*\*\s*[:：]\s*([A-Z][A-Z0-9_-]+(?:-[A-Z0-9]+)*)"
)

# Match both checked/unchecked:  - [ ] AC-N:  / - [x] AC-N:  / - [x] **AC-N**:
AC_PATTERN = re.compile(
    r"- \[[ xX]\]\s+\*?\*?(?P<ac>AC-\d+)\*?\*?\s*[:：]\s*(?P<desc>.+)"
)

# Section headers that contain acceptance criteria
AC_SECTION_PATTERNS = [
    re.compile(r"^#+\s+.*(?:인수 기준|Acceptance Criteria)", re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# Spec Parsing
# ---------------------------------------------------------------------------

def find_spec_files() -> list[Path]:
    """Recursively find all .md files in docs/specs/."""
    if not SPECS_DIR.exists():
        print(f"[WARN] Specs directory not found: {SPECS_DIR}")
        return []
    return sorted(SPECS_DIR.rglob("*.md"))


def parse_spec_id(content: str) -> str | None:
    """Extract the Spec ID from file content."""
    match = SPEC_ID_PATTERN.search(content)
    return match.group(1) if match else None


def parse_acceptance_criteria(content: str) -> list[tuple[str, str]]:
    """Extract (AC-N, description) tuples from the AC section."""
    acs: list[tuple[str, str]] = []
    in_ac_section = False

    for line in content.splitlines():
        # Check if we entered an AC section
        for pattern in AC_SECTION_PATTERNS:
            if pattern.match(line.strip()):
                in_ac_section = True
                break

        # Check if we left the AC section (next same-level or higher heading)
        # Sub-headings (###) within the AC section are allowed (e.g., Phase groupings)
        if in_ac_section and re.match(r"^#{1,2}\s", line) and not any(
            p.match(line.strip()) for p in AC_SECTION_PATTERNS
        ):
            in_ac_section = False

        if in_ac_section:
            match = AC_PATTERN.match(line.strip())
            if match:
                acs.append((match.group("ac"), match.group("desc").strip()))

    return acs


def parse_spec_file(path: Path) -> tuple[str | None, list[tuple[str, str]]]:
    """Parse a spec file and return (spec_id, [(ac_id, description), ...])."""
    content = path.read_text(encoding="utf-8")
    spec_id = parse_spec_id(content)
    acs = parse_acceptance_criteria(content)
    return spec_id, acs


# ---------------------------------------------------------------------------
# Test File Mapping
# ---------------------------------------------------------------------------

def spec_id_to_test_filename(spec_id: str) -> str:
    """Map Spec ID to test file name per TEST_STRATEGY.md Section 2.1.

    Examples:
        FS-KPI-001 -> test_kpi_spec.py
        FS-AI-010 -> test_ai_010_spec.py
        FS-AI-RAG-001 -> test_ai_rag_spec.py
        FS-ADMIN-003 -> test_admin_003_spec.py
        FS-DASH-004 -> test_dash_004_spec.py
        DM-MIG-001 -> test_dm_mig_spec.py
        CFG-001 -> test_cfg_spec.py
        API-ERR-001 -> test_api_err_spec.py
        SVC-001 -> test_svc_spec.py
        FS-SCHEMA-001 -> test_schema_spec.py
    """
    # Normalize: strip FS- prefix if present, lowercase, replace - with _
    sid = spec_id
    if sid.startswith("FS-"):
        sid = sid[3:]

    parts = sid.lower().split("-")

    # Build filename: use all parts except trailing numeric as suffix
    # e.g., AI-010 -> ai_010, KPI-001 -> kpi, ADMIN-003 -> admin_003
    # AI-RAG-001 -> ai_rag
    name_parts = []
    for i, part in enumerate(parts):
        name_parts.append(part)

    name = "_".join(name_parts)
    return f"test_{name}_spec.py"


def ac_to_function_prefix(spec_id: str, ac_id: str) -> str:
    """Build the test function name prefix for matching.

    FS-KPI-001 AC-1 -> test_fs_kpi_001_ac1
    """
    sid = spec_id.lower().replace("-", "_")
    ac_num = ac_id.lower().replace("-", "")
    return f"test_{sid}_{ac_num}"


def slugify_description(desc: str, max_len: int = 50) -> str:
    """Convert AC description to a snake_case function name suffix."""
    # Remove markdown formatting
    desc = re.sub(r"[`*\[\]()]", "", desc)
    # Remove Korean characters and special chars, keep alphanumeric and spaces
    desc = re.sub(r"[^\w\s]", " ", desc, flags=re.ASCII)
    # If description is mostly non-ASCII (Korean), generate a simple suffix
    ascii_chars = sum(1 for c in desc if c.isascii() and c.isalnum())
    if ascii_chars < 5:
        return ""
    # Normalize whitespace and convert to snake_case
    words = desc.strip().split()
    slug = "_".join(w.lower() for w in words if w)
    return slug[:max_len].rstrip("_")


# ---------------------------------------------------------------------------
# Existing Test Detection
# ---------------------------------------------------------------------------

def find_existing_test_functions(test_dir: Path) -> set[str]:
    """Collect all test function name prefixes from existing test files."""
    prefixes: set[str] = set()
    if not test_dir.exists():
        return prefixes

    for py_file in test_dir.glob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        for match in re.finditer(r"(?:def|async\s+def)\s+(test_\w+)", content):
            prefixes.add(match.group(1))

    return prefixes


def check_ac_covered(
    spec_id: str,
    ac_id: str,
    existing_functions: set[str],
) -> bool:
    """Check if an AC already has a corresponding test function."""
    prefix = ac_to_function_prefix(spec_id, ac_id)
    return any(fn.startswith(prefix) for fn in existing_functions)


# ---------------------------------------------------------------------------
# Also scan for spec_ref markers and comment-based Spec refs
# ---------------------------------------------------------------------------

def find_spec_refs_in_tests(test_dir: Path) -> set[str]:
    """Find all spec_ref("SPEC", "AC") markers and '# Spec: SPEC AC-N' comments."""
    covered: set[str] = set()
    if not test_dir.exists():
        return covered

    for py_file in test_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        # Match @spec_ref("FS-AI-010", "AC-1") markers
        for m in re.finditer(
            r'spec_ref\(\s*["\']([^"\']+)["\']\s*,\s*["\']([^"\']+)["\']\s*\)',
            content,
        ):
            covered.add(f"{m.group(1)}:{m.group(2)}")
        # Match # Spec: FS-DASH-004 AC-1 comments
        for m in re.finditer(
            r"#\s*Spec:\s+(\S+)\s+(AC-\d+)",
            content,
        ):
            covered.add(f"{m.group(1)}:{m.group(2)}")

    return covered


# ---------------------------------------------------------------------------
# Stub Generation
# ---------------------------------------------------------------------------

STUB_TEMPLATE = '''\
@spec_ref("{spec_id}", "{ac_id}")
async def {func_name}():
    """{spec_id} {ac_id}: {description}"""
    # TODO: Implement test -- auto-generated from Spec
    pytest.skip("Auto-generated stub -- implement test")
'''

FILE_HEADER_TEMPLATE = '''\
# Spec: {spec_id}
"""Auto-generated test stubs for {spec_id} Acceptance Criteria.

Generated by: uv run python -m scripts.gen_spec_tests
Strategy: TEST-STRATEGY-001

IMPORTANT: Implement each test stub by replacing pytest.skip() with real assertions.
Do NOT delete the @spec_ref decorator -- it enables AC tracking in CI.
"""

import pytest

from tests.conftest import spec_ref


'''


def generate_stubs(
    spec_id: str,
    missing_acs: list[tuple[str, str]],
) -> str:
    """Generate test stub code for missing ACs."""
    stubs = []
    for ac_id, description in missing_acs:
        slug = slugify_description(description)
        if slug:
            func_name = f"{ac_to_function_prefix(spec_id, ac_id)}_{slug}"
        else:
            func_name = ac_to_function_prefix(spec_id, ac_id)

        stubs.append(
            STUB_TEMPLATE.format(
                spec_id=spec_id,
                ac_id=ac_id,
                func_name=func_name,
                description=description,
            )
        )

    return "\n".join(stubs)


def append_stubs_to_file(
    test_file: Path,
    spec_id: str,
    stubs_code: str,
) -> None:
    """Append stubs to an existing file, or create a new file with header."""
    if test_file.exists():
        existing = test_file.read_text(encoding="utf-8")
        # Ensure spec_ref import exists
        if "from tests.conftest import spec_ref" not in existing:
            # Insert import after the last import line
            lines = existing.splitlines(keepends=True)
            insert_idx = 0
            for i, line in enumerate(lines):
                if line.strip().startswith(("import ", "from ")):
                    insert_idx = i + 1
            lines.insert(insert_idx, "from tests.conftest import spec_ref\n")
            existing = "".join(lines)

        with test_file.open("w", encoding="utf-8") as f:
            f.write(existing.rstrip() + "\n\n\n" + stubs_code)
    else:
        header = FILE_HEADER_TEMPLATE.format(spec_id=spec_id)
        with test_file.open("w", encoding="utf-8") as f:
            f.write(header + stubs_code)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print("  Spec-Driven Test Stub Generator")
    print("  TEST-STRATEGY-001")
    print("=" * 60)
    print()

    # Gather existing test functions from all test directories
    existing_funcs: set[str] = set()
    for test_subdir in ["unit", "api", "integration"]:
        test_path = BACKEND_DIR / "tests" / test_subdir
        existing_funcs |= find_existing_test_functions(test_path)

    # Also check root tests/ dir
    existing_funcs |= find_existing_test_functions(BACKEND_DIR / "tests")

    # Find spec_ref markers
    spec_refs = find_spec_refs_in_tests(BACKEND_DIR / "tests")

    print(f"Found {len(existing_funcs)} existing test functions")
    print(f"Found {len(spec_refs)} spec_ref markers")
    print()

    # Parse all spec files
    spec_files = find_spec_files()
    print(f"Scanning {len(spec_files)} spec files in {SPECS_DIR}")
    print()

    total_specs = 0
    total_acs = 0
    total_covered = 0
    total_generated = 0

    for spec_file in spec_files:
        spec_id, acs = parse_spec_file(spec_file)
        if not spec_id or not acs:
            continue

        total_specs += 1
        total_acs += len(acs)

        # Determine which ACs are missing
        missing_acs: list[tuple[str, str]] = []
        for ac_id, desc in acs:
            # Check by function name prefix OR spec_ref marker
            fn_covered = check_ac_covered(spec_id, ac_id, existing_funcs)
            ref_covered = f"{spec_id}:{ac_id}" in spec_refs
            if fn_covered or ref_covered:
                total_covered += 1
            else:
                missing_acs.append((ac_id, desc))

        if missing_acs:
            test_filename = spec_id_to_test_filename(spec_id)
            test_file = TESTS_UNIT_DIR / test_filename
            stubs_code = generate_stubs(spec_id, missing_acs)
            append_stubs_to_file(test_file, spec_id, stubs_code)
            total_generated += len(missing_acs)
            print(
                f"  {spec_id}: generated {len(missing_acs)} stubs "
                f"-> {test_file.relative_to(BACKEND_DIR)}"
            )
        else:
            rel = spec_file.relative_to(PROJECT_ROOT)
            print(f"  {spec_id}: all {len(acs)} ACs covered ({rel})")

    print()
    print("-" * 60)
    print(f"  Specs processed:     {total_specs}")
    print(f"  Total ACs found:     {total_acs}")
    print(f"  ACs already covered: {total_covered}")
    print(f"  Stubs generated:     {total_generated}")
    print("-" * 60)

    if total_generated > 0:
        print()
        print(
            f"Generated {total_generated} stubs for {total_specs} specs. "
            f"{total_covered} ACs already covered."
        )
        print("Run: uv run pytest tests/ -v  to see the AC summary.")
    else:
        print()
        print("All ACs are covered. No stubs generated.")


if __name__ == "__main__":
    main()
