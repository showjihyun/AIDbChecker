# Spec: TEST-STRATEGY-001
"""Shared Spec parsing utilities for harness engineering tools.

Provides common functions for:
- Finding spec files in docs/specs/
- Parsing Spec IDs, metadata, acceptance criteria
- Mapping Spec IDs to test filenames

Reused by: gen_spec_tests.py, validate_spec.py, spec_dashboard.py
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent
SPECS_DIR = PROJECT_ROOT / "docs" / "specs"
TESTS_DIR = BACKEND_DIR / "tests"

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

# Metadata patterns
STATUS_PATTERN = re.compile(
    r"\*\*상태\*\*\s*[:：]\s*(Draft|Approved|Implemented)", re.IGNORECASE
)
PRIORITY_PATTERN = re.compile(
    r"\*\*우선순위\*\*\s*[:：]\s*(P[0-3])"
)
DEPENDENCY_PATTERN = re.compile(
    r"\*\*선행 Spec\*\*\s*[:：]\s*(.+)"
)
IMPL_FILES_PATTERN = re.compile(
    r"\*\*구현 파일\*\*\s*[:：]"
)

# ANSI color codes
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    DIM = "\033[2m"
    WHITE = "\033[97m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_BLUE = "\033[44m"


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass
class AcceptanceCriterion:
    ac_id: str       # e.g., "AC-1"
    description: str  # e.g., "GET /api/v1/instances/{id}/kpi returns 12 KPIs"


@dataclass
class SpecMetadata:
    spec_id: str | None = None
    status: str | None = None
    priority: str | None = None
    dependencies: list[str] = field(default_factory=list)
    has_impl_files: bool = False
    has_api_endpoints: bool = False
    has_schemas: bool = False
    has_code_blocks: bool = False
    acceptance_criteria: list[AcceptanceCriterion] = field(default_factory=list)
    file_path: Path | None = None


# ---------------------------------------------------------------------------
# Parsing Functions
# ---------------------------------------------------------------------------

def find_spec_files() -> list[Path]:
    """Recursively find all .md files in docs/specs/."""
    if not SPECS_DIR.exists():
        return []
    # Exclude SPEC_TEMPLATE.md
    return sorted(
        p for p in SPECS_DIR.rglob("*.md")
        if p.name != "SPEC_TEMPLATE.md"
    )


def parse_spec_id(content: str) -> str | None:
    """Extract the Spec ID from file content."""
    match = SPEC_ID_PATTERN.search(content)
    return match.group(1) if match else None


def parse_acceptance_criteria(content: str) -> list[AcceptanceCriterion]:
    """Extract acceptance criteria from the AC section of a spec file."""
    acs: list[AcceptanceCriterion] = []
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
                acs.append(AcceptanceCriterion(
                    ac_id=match.group("ac"),
                    description=match.group("desc").strip(),
                ))

    return acs


def parse_status(content: str) -> str | None:
    """Extract the status field from spec metadata."""
    match = STATUS_PATTERN.search(content)
    return match.group(1) if match else None


def parse_priority(content: str) -> str | None:
    """Extract the priority field from spec metadata."""
    match = PRIORITY_PATTERN.search(content)
    return match.group(1) if match else None


def parse_dependencies(content: str) -> list[str]:
    """Extract dependency Spec IDs from the metadata."""
    match = DEPENDENCY_PATTERN.search(content)
    if not match:
        return []
    dep_text = match.group(1).strip()
    if dep_text.lower() in ("없음", "none", "-", ""):
        return []
    # Extract Spec IDs from text like "DM-001 (ERD), API-001 (인증)"
    return re.findall(r"([A-Z][A-Z0-9]+-[A-Z0-9-]+)", dep_text)


def has_api_endpoints(content: str) -> bool:
    """Check if the spec defines API endpoints (table with Method/Path)."""
    return bool(re.search(
        r"\|\s*(?:GET|POST|PUT|DELETE|PATCH)\s*\|", content
    ))


def has_request_response_schemas(content: str) -> bool:
    """Check if the spec defines Request/Response schemas."""
    return bool(re.search(
        r"(?:Request|Response|class\s+\w+(?:Request|Response))", content
    ))


def has_impl_files_section(content: str) -> bool:
    """Check if the spec has an implementation files section."""
    return bool(IMPL_FILES_PATTERN.search(content))


def count_code_blocks(content: str) -> int:
    """Count the number of fenced code blocks in the content."""
    return len(re.findall(r"^```", content, re.MULTILINE)) // 2


def parse_spec_file(path: Path) -> SpecMetadata:
    """Parse a spec file and return its full metadata."""
    content = path.read_text(encoding="utf-8")
    return SpecMetadata(
        spec_id=parse_spec_id(content),
        status=parse_status(content),
        priority=parse_priority(content),
        dependencies=parse_dependencies(content),
        has_impl_files=has_impl_files_section(content),
        has_api_endpoints=has_api_endpoints(content),
        has_schemas=has_request_response_schemas(content),
        has_code_blocks=count_code_blocks(content) > 0,
        acceptance_criteria=parse_acceptance_criteria(content),
        file_path=path,
    )


def parse_all_specs() -> list[SpecMetadata]:
    """Parse all spec files and return their metadata."""
    specs = []
    for path in find_spec_files():
        meta = parse_spec_file(path)
        if meta.spec_id:
            specs.append(meta)
    return specs


# ---------------------------------------------------------------------------
# Test Mapping Utilities
# ---------------------------------------------------------------------------

def spec_id_to_test_filename(spec_id: str) -> str:
    """Map Spec ID to test file name per TEST_STRATEGY.md Section 2.1."""
    sid = spec_id
    if sid.startswith("FS-"):
        sid = sid[3:]
    parts = sid.lower().split("-")
    name = "_".join(parts)
    return f"test_{name}_spec.py"


def ac_to_function_prefix(spec_id: str, ac_id: str) -> str:
    """Build the test function name prefix for matching."""
    sid = spec_id.lower().replace("-", "_")
    ac_num = ac_id.lower().replace("-", "")
    return f"test_{sid}_{ac_num}"


def find_existing_test_functions(test_dir: Path) -> set[str]:
    """Collect all test function names from test files."""
    funcs: set[str] = set()
    if not test_dir.exists():
        return funcs
    for py_file in test_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        for match in re.finditer(r"(?:def|async\s+def)\s+(test_\w+)", content):
            funcs.add(match.group(1))
    return funcs


def find_spec_refs_in_tests(test_dir: Path) -> dict[str, list[str]]:
    """Find spec_ref markers and Spec comments in tests.

    Returns a dict mapping "SPEC_ID:AC-N" -> list of test function names.
    """
    refs: dict[str, list[str]] = {}
    if not test_dir.exists():
        return refs

    for py_file in test_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")

        # Current function context tracker
        current_func = None
        for line in content.splitlines():
            func_match = re.match(r"\s*(?:async\s+)?def\s+(test_\w+)", line)
            if func_match:
                current_func = func_match.group(1)

            # Match @spec_ref("FS-AI-010", "AC-1")
            for m in re.finditer(
                r'spec_ref\(\s*["\']([^"\']+)["\']\s*,\s*["\']([^"\']+)["\']\s*\)',
                line,
            ):
                key = f"{m.group(1)}:{m.group(2)}"
                refs.setdefault(key, []).append(current_func or "unknown")

            # Match # Spec: FS-DASH-004 AC-1
            for m in re.finditer(r"#\s*Spec:\s+(\S+)\s+(AC-\d+)", line):
                key = f"{m.group(1)}:{m.group(2)}"
                refs.setdefault(key, []).append(current_func or "unknown")

    return refs


def get_all_known_spec_ids() -> set[str]:
    """Get all known Spec IDs from the specs directory."""
    ids = set()
    for path in find_spec_files():
        content = path.read_text(encoding="utf-8")
        sid = parse_spec_id(content)
        if sid:
            ids.add(sid)
    return ids
