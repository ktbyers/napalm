"""Self-consistency checks for the Pydantic models in ``napalm.base.models``.

These tests do not exercise any driver -- they verify that:

1. Every model in the public ``ALL_MODELS`` registry can produce a JSON Schema
   (i.e. has no construction-time inconsistency).
2. Every getter / ping / traceroute / is_alive method declared on
   ``NetworkDriver`` resolves to a ``models.X`` annotation via
   ``models.getter_return_annotation``.
"""

from __future__ import annotations

import inspect
import typing

import pytest
from pydantic import BaseModel

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
# 2. getter_return_annotation() resolves every contract method
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
def test_getter_return_annotation_resolves(method_name):
    """``models.getter_return_annotation`` returns an annotation containing a NAPALM model."""
    annotation = models.getter_return_annotation(method_name)
    assert _annotation_contains_model(annotation), (
        f"NetworkDriver.{method_name} return annotation does not reference a "
        f"BaseModel: {annotation!r}"
    )
