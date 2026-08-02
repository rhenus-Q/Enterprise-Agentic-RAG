"""Field-name parity between server/schemas.py and frontend/src/api/types.ts.

`frontend/src/api/types.ts` is a hand-maintained mirror of the Pydantic API
contract, and nothing else in the project fails when the two drift: `tsc
--noEmit` only proves the frontend agrees with its own copy, and the rest of
tests/server/ only proves the backend agrees with Pydantic. Renaming a field on
one side ships green through all three CI jobs and breaks in the browser.

These tests compare the two field-name sets directly, in both directions.

Scope is deliberately narrow: field *names* only. TypeScript types, nullability
and nesting are not compared — that would need a real TypeScript parser, while
the realistic failure is a renamed, added, or forgotten field. The parser below
is intentionally small and local: it reads one interface block at a time, so a
field name that exists in some *other* interface cannot satisfy the check.
"""

import re
from pathlib import Path
from typing import NamedTuple

import pytest

from server import schemas

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TYPES_TS = PROJECT_ROOT / "frontend" / "src" / "api" / "types.ts"

# Pydantic model name -> the TypeScript interface mirroring it. The mapping is
# explicit rather than inferred because the two sides do not always agree on the
# name: the backend's CancelResponse is CancelRunResponse in the frontend.
MODEL_TO_INTERFACE = {
    "AskResponse": "AskResponse",
    "CancelResponse": "CancelRunResponse",
    "Citation": "Citation",
    "DocumentsResponse": "DocumentsResponse",
    "IndexStatus": "IndexStatus",
    "NodeTiming": "NodeTiming",
    "PreflightStatus": "PreflightStatus",
    "RunDetail": "RunDetail",
    "RunRuntime": "RunRuntime",
    "RunSummary": "RunSummary",
    "RuntimeStatus": "RuntimeStatus",
}


class TsInterface(NamedTuple):
    """One parsed `export interface` block: its own fields and its parents."""

    fields: frozenset[str]
    extends: tuple[str, ...]


_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT_RE = re.compile(r"//.*")
_INTERFACE_HEADER_RE = re.compile(
    r"\bexport\s+interface\s+(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)(?P<heritage>[^{]*)\{"
)
_EXTENDS_RE = re.compile(r"\bextends\s+(?P<parents>[^{]+)")
# A member declaration: `field: Type` or `field?: Type`.
_MEMBER_RE = re.compile(r"^(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)\s*\??\s*:")


def _strip_comments(source: str) -> str:
    """Remove block comments first, so `//` inside one cannot survive."""

    return _LINE_COMMENT_RE.sub("", _BLOCK_COMMENT_RE.sub("", source))


def _block_body(source: str, open_brace_index: int) -> str:
    """Return the text between `{` at `open_brace_index` and its matching `}`."""

    depth = 0
    for index in range(open_brace_index, len(source)):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[open_brace_index + 1 : index]

    raise AssertionError(f"Unbalanced braces in {TYPES_TS} at offset {open_brace_index}")


def _split_members(body: str) -> list[str]:
    """Split an interface body on its top-level `;` separators.

    Brace/bracket/paren depth is tracked so a `;` inside an inline object type
    does not split a member and expose its inner field names.
    """

    members: list[str] = []
    current: list[str] = []
    depth = 0

    for char in body:
        if char in "{[(":
            depth += 1
        elif char in "}])":
            depth -= 1
        elif char == ";" and depth == 0:
            members.append("".join(current))
            current = []
            continue
        current.append(char)

    members.append("".join(current))
    return [member.strip() for member in members if member.strip()]


def _parse_interfaces(source: str) -> dict[str, TsInterface]:
    interfaces: dict[str, TsInterface] = {}
    stripped = _strip_comments(source)

    for header in _INTERFACE_HEADER_RE.finditer(stripped):
        body = _block_body(stripped, header.end() - 1)
        fields = {
            match.group("name")
            for match in (_MEMBER_RE.match(member) for member in _split_members(body))
            if match is not None
        }

        extends_match = _EXTENDS_RE.search(header.group("heritage"))
        parents = (
            tuple(
                part.strip() for part in extends_match.group("parents").split(",") if part.strip()
            )
            if extends_match
            else ()
        )
        interfaces[header.group("name")] = TsInterface(frozenset(fields), parents)

    return interfaces


def _resolved_fields(interfaces: dict[str, TsInterface], name: str) -> frozenset[str]:
    """Own fields plus every inherited one, so `extends` mirrors Pydantic subclassing."""

    interface = interfaces[name]
    resolved = set(interface.fields)

    for parent in interface.extends:
        assert parent in interfaces, (
            f"{name} extends {parent}, which {TYPES_TS.name} does not declare."
        )
        resolved |= _resolved_fields(interfaces, parent)

    return frozenset(resolved)


@pytest.fixture(scope="module")
def ts_interfaces() -> dict[str, TsInterface]:
    assert TYPES_TS.is_file(), f"Expected the frontend API contract at {TYPES_TS}"
    return _parse_interfaces(TYPES_TS.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("model_name", "interface_name"),
    sorted(MODEL_TO_INTERFACE.items()),
    ids=sorted(MODEL_TO_INTERFACE),
)
def test_model_and_interface_declare_the_same_field_names(
    model_name: str, interface_name: str, ts_interfaces: dict[str, TsInterface]
) -> None:
    model = getattr(schemas, model_name, None)
    assert model is not None, (
        f"server/schemas.py no longer defines {model_name}; update MODEL_TO_INTERFACE "
        f"here and in {TYPES_TS.name}."
    )
    assert interface_name in ts_interfaces, (
        f"{TYPES_TS.name} no longer declares `export interface {interface_name}`, "
        f"which mirrors {model_name} in server/schemas.py."
    )

    python_fields = set(model.model_fields)
    typescript_fields = set(_resolved_fields(ts_interfaces, interface_name))

    missing_in_typescript = sorted(python_fields - typescript_fields)
    missing_in_python = sorted(typescript_fields - python_fields)

    assert not missing_in_typescript and not missing_in_python, (
        f"The API contract has drifted between server/schemas.py::{model_name} and "
        f"frontend/src/api/types.ts::{interface_name}.\n"
        f"  in Python but missing from TypeScript: {missing_in_typescript or 'none'}\n"
        f"  in TypeScript but missing from Python: {missing_in_python or 'none'}"
    )


def test_every_mapped_model_is_a_pydantic_model() -> None:
    for model_name in MODEL_TO_INTERFACE:
        model = getattr(schemas, model_name)
        assert hasattr(model, "model_fields"), f"{model_name} is not a Pydantic model"
        assert model.model_fields, f"{model_name} declares no fields"


def test_each_interface_is_read_in_isolation(ts_interfaces: dict[str, TsInterface]) -> None:
    # A whole-file substring check would pass on `duration_ms` for every model,
    # because NodeTiming declares it. Parity is only meaningful per interface.
    assert "duration_ms" in ts_interfaces["NodeTiming"].fields
    assert "duration_ms" not in ts_interfaces["AskResponse"].fields
    assert "total_duration_ms" in ts_interfaces["AskResponse"].fields
    assert "total_duration_ms" not in ts_interfaces["NodeTiming"].fields


def test_optional_typescript_fields_are_parsed(ts_interfaces: dict[str, TsInterface]) -> None:
    # `signal?: AbortSignal` — the `?` must not hide the field name from the parser.
    assert ts_interfaces["AskOptions"].fields == frozenset({"signal"})


def test_inherited_typescript_fields_are_resolved(ts_interfaces: dict[str, TsInterface]) -> None:
    # RunDetail extends RunSummary in TypeScript and subclasses it in Pydantic;
    # model_fields includes inherited fields, so the TypeScript side must too.
    assert ts_interfaces["RunDetail"].extends == ("RunSummary",)
    assert "run_id" not in ts_interfaces["RunDetail"].fields
    assert "run_id" in _resolved_fields(ts_interfaces, "RunDetail")
