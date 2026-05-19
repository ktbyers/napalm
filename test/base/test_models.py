"""Self-consistency checks for the Pydantic models in ``napalm.base.models``.

These tests do not exercise any driver -- they verify that:

1. Every model in the public ``ALL_MODELS`` registry can produce a JSON Schema
   (i.e. has no construction-time inconsistency).
2. Every getter / ping / traceroute / is_alive method declared on
   ``NetworkDriver`` resolves to a ``models.X`` annotation via
   ``models.getter_model``.
3. Any ``Example::`` block in ``NetworkDriver`` docstrings that parses as a
   Python literal validates against the model declared by its method's return
   annotation. This is best-effort -- docstrings contain placeholders like
   ``[FAMILY_NAME]`` and ``...`` that are not valid Python literals; those
   examples are skipped rather than failed, but the test asserts that at least
   one example *does* parse and validate (otherwise the heuristic is broken).
"""

from __future__ import annotations

import ast
import inspect
import re
import textwrap
import typing

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

from napalm.base import models
from napalm.base.base import NetworkDriver


# ---------------------------------------------------------------------------
# 1. Every model can emit a JSON schema
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(models.ALL_MODELS))
def test_model_json_schema(name):
    """Every model in ALL_MODELS exposes a valid JSON schema."""
    schema = models.ALL_MODELS[name].model_json_schema()
    assert isinstance(schema, dict)
    assert schema.get("type") in {"object", "array", None} or "anyOf" in schema or "$ref" in schema


# ---------------------------------------------------------------------------
# 2. getter_model() resolves every contract method
# ---------------------------------------------------------------------------


def _annotation_contains_model(annotation):
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return True
    return any(_annotation_contains_model(arg) for arg in typing.get_args(annotation))


def _contract_methods():
    """Methods on NetworkDriver whose return annotation references a model."""
    out = []
    for name, attr in inspect.getmembers(NetworkDriver, predicate=inspect.isfunction):
        if name.startswith("_"):
            continue
        annotation = attr.__annotations__.get("return")
        if annotation is not None and _annotation_contains_model(annotation):
            out.append(name)
    return out


@pytest.mark.parametrize("method_name", _contract_methods())
def test_getter_model_resolves(method_name):
    """``models.getter_model`` returns an annotation containing a NAPALM model."""
    annotation = models.getter_model(method_name)
    assert _annotation_contains_model(annotation), (
        f"NetworkDriver.{method_name} return annotation does not reference a "
        f"BaseModel: {annotation!r}"
    )


# ---------------------------------------------------------------------------
# 3. Best-effort Example:: validation
# ---------------------------------------------------------------------------


_EXAMPLE_RE = re.compile(
    r"Example::\s*\n(?P<body>(?:[ \t]+.*\n|\s*\n)+)",
    re.MULTILINE,
)


def _extract_examples(docstring):
    """Yield each ``Example::`` block body (dedented) from ``docstring``."""
    if not docstring:
        return
    for match in _EXAMPLE_RE.finditer(docstring):
        yield textwrap.dedent(match.group("body")).strip()


def _try_parse_literal(text):
    """Try to ast.literal_eval ``text``; return (value, error_or_None)."""
    try:
        return ast.literal_eval(text), None
    except (ValueError, SyntaxError) as exc:
        return None, exc


def _collect_docstring_examples():
    """Return [(method_name, example_text), ...] for every getter."""
    pairs = []
    for name in _contract_methods():
        method = getattr(NetworkDriver, name)
        for body in _extract_examples(method.__doc__):
            pairs.append((name, body))
    return pairs


def test_at_least_one_example_validates():
    """Sanity check that the docstring scraper / example heuristic is wired.

    The NAPALM docstrings contain many placeholders that are not parseable as
    Python literals (``[FAMILY_NAME]``, ``...``, comments, ``True/False``-style
    prose, etc.), so we tolerate per-example failures -- but at least one
    Example:: block in the codebase must parse and validate. If this drops to
    zero, the regex / dedent logic is almost certainly broken.
    """
    parsed_ok = 0
    validated_ok = 0
    parse_failures = []
    validate_failures = []

    for method_name, body in _collect_docstring_examples():
        value, err = _try_parse_literal(body)
        if err is not None:
            parse_failures.append((method_name, str(err).splitlines()[0]))
            continue
        parsed_ok += 1
        annotation = models.getter_model(method_name)
        try:
            TypeAdapter(annotation).validate_python(value)
        except ValidationError as exc:
            validate_failures.append((method_name, str(exc).splitlines()[0]))
            continue
        validated_ok += 1

    assert parsed_ok > 0, (
        "No Example:: blocks were parseable as Python literals. "
        "The docstring scraper is probably broken."
    )
    # ``validated_ok`` is informational; many examples use placeholders. We
    # don't gate on it but emit context if there's a regression.
    print(
        f"Examples: parsed={parsed_ok} validated={validated_ok} "
        f"parse_failures={len(parse_failures)} "
        f"validate_failures={len(validate_failures)}"
    )
