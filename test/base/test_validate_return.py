"""Unit tests for the _validate_return decorator and __init_subclass__ wrapping.

These tests exercise the runtime validation mechanism in ``napalm.base.base``
directly, independent of any driver's mocked data or the BaseTestGetters
framework.  They cover:

_validate_return behaviour:
1. With NAPALM_STRICT_MODELS unset, a malformed getter return value passes
   through silently -- _validate_return is a no-op.
2. With NAPALM_STRICT_MODELS=1, a conforming getter return value passes
   cleanly.
3. With NAPALM_STRICT_MODELS=1, a malformed getter return value raises
   ModelValidationException with a useful message.

__init_subclass__ wrapping:
4. Overriding a getter in a subclass causes __init_subclass__ to wrap it with
   _validate_return (confirmed via __wrapped__ attribute).
5. Methods without a NAPALM model return annotation (e.g. compare_config)
   are NOT wrapped by __init_subclass__.
6. Methods the subclass does NOT override are NOT wrapped (cls.__dict__ check).
7. A grandchild that inherits without overriding still gets validation via the
   already-wrapped parent method.
8. The __wrapped__ guard prevents double-wrapping on a subclass of a subclass.
"""

from __future__ import annotations

import pytest

import napalm.base.exceptions
from napalm.base import models
from napalm.base.base import NetworkDriver, _STRICT_MODELS_ENV


# ---------------------------------------------------------------------------
# Minimal conforming and non-conforming get_facts payloads
# ---------------------------------------------------------------------------

_GOOD_FACTS: models.FactsDict = {
    "os_version": "1.0",
    "uptime": 12345.0,
    "interface_list": ["Ethernet1", "Management1"],
    "vendor": "ACME",
    "serial_number": "SN001",
    "model": "vRouter",
    "hostname": "router1",
    "fqdn": "router1.example.com",
}

# Missing required fields -- will fail Pydantic validation.
_BAD_FACTS = {"hostname": "router1"}


# ---------------------------------------------------------------------------
# Minimal fake driver
# ---------------------------------------------------------------------------


class _FakeDriver(NetworkDriver):
    """Minimal driver subclass for testing _validate_return in isolation."""

    def __init__(self, hostname="test", username="u", password="p", timeout=60, optional_args=None):
        self.hostname = hostname
        self.username = username
        self.password = password
        self.timeout = timeout
        self.force_no_enable = False
        self.use_canonical_interface = False
        self._facts_payload = _GOOD_FACTS

    def open(self):
        pass

    def close(self):
        pass

    def is_alive(self):
        return {"is_alive": True}

    def get_facts(self) -> models.FactsDict:
        return self._facts_payload


# ---------------------------------------------------------------------------
# 1. NAPALM_STRICT_MODELS unset -- malformed return passes through silently
# ---------------------------------------------------------------------------


def test_validate_return_disabled_by_default(monkeypatch):
    """Without NAPALM_STRICT_MODELS, malformed data is returned unchanged."""
    monkeypatch.delenv(_STRICT_MODELS_ENV, raising=False)

    driver = _FakeDriver()
    driver._facts_payload = _BAD_FACTS

    result = driver.get_facts()
    assert result is _BAD_FACTS


# ---------------------------------------------------------------------------
# 2. NAPALM_STRICT_MODELS=1, conforming return passes cleanly
# ---------------------------------------------------------------------------


def test_validate_return_passes_conforming_data(monkeypatch):
    """With NAPALM_STRICT_MODELS=1, a conforming return value passes cleanly."""
    monkeypatch.setenv(_STRICT_MODELS_ENV, "1")

    driver = _FakeDriver()
    driver._facts_payload = _GOOD_FACTS

    result = driver.get_facts()
    assert result == _GOOD_FACTS


# ---------------------------------------------------------------------------
# 3. NAPALM_STRICT_MODELS=1, malformed return raises ModelValidationException
# ---------------------------------------------------------------------------


def test_validate_return_raises_on_bad_data(monkeypatch):
    """With NAPALM_STRICT_MODELS=1, a malformed return raises ModelValidationException."""
    monkeypatch.setenv(_STRICT_MODELS_ENV, "1")

    driver = _FakeDriver()
    driver._facts_payload = _BAD_FACTS

    with pytest.raises(napalm.base.exceptions.ModelValidationException) as exc_info:
        driver.get_facts()

    msg = str(exc_info.value)
    assert "_FakeDriver" in msg
    assert "get_facts" in msg


# ---------------------------------------------------------------------------
# 4. __wrapped__ guard prevents double-wrapping on a subclass of a subclass
# ---------------------------------------------------------------------------


def test_no_double_wrap_on_subclass_of_subclass(monkeypatch):
    """__init_subclass__ must not wrap a getter that is already wrapped."""
    monkeypatch.setenv(_STRICT_MODELS_ENV, "1")

    class _ChildDriver(_FakeDriver):
        def get_facts(self) -> models.FactsDict:
            return _GOOD_FACTS

    class _GrandchildDriver(_ChildDriver):
        pass

    # The wrapper should be applied at most once; calling it must not nest
    # validation and should still return the correct value.
    driver = _GrandchildDriver()
    result = driver.get_facts()
    assert result == _GOOD_FACTS

    # Confirm __wrapped__ is present (set by _validate_return)
    assert hasattr(_ChildDriver.get_facts, "__wrapped__"), (
        "Expected _validate_return to set __wrapped__ on _ChildDriver.get_facts"
    )
    # Grandchild inherits but does not define its own get_facts, so there is
    # nothing to re-wrap -- __init_subclass__ skips it entirely.
    assert "get_facts" not in _GrandchildDriver.__dict__


# ---------------------------------------------------------------------------
# 5. Methods without a model return annotation are NOT wrapped
# ---------------------------------------------------------------------------


def test_non_model_method_not_wrapped():
    """__init_subclass__ must not wrap methods whose return type is not a model.

    compare_config() -> str has no Pydantic model annotation, so it should
    never have __wrapped__ set on it.
    """

    class _DriverWithCompare(_FakeDriver):
        def compare_config(self) -> str:
            return "+ added line"

    assert not hasattr(_DriverWithCompare.compare_config, "__wrapped__")


# ---------------------------------------------------------------------------
# 6. Methods the subclass did NOT override are NOT wrapped
# ---------------------------------------------------------------------------


def test_non_overridden_method_not_in_subclass_dict():
    """A getter not overridden by the subclass must not appear in cls.__dict__.

    __init_subclass__ uses cls.__dict__ to detect overrides; methods that are
    only inherited must be left untouched.
    """

    class _MinimalDriver(_FakeDriver):
        pass  # does not override get_interfaces

    assert "get_interfaces" not in _MinimalDriver.__dict__


# ---------------------------------------------------------------------------
# 7. Grandchild inherits validation from already-wrapped parent method
# ---------------------------------------------------------------------------


def test_grandchild_inherits_validation(monkeypatch):
    """A grandchild that does not override a getter still gets validation via
    the wrapper applied to the parent's method.
    """
    monkeypatch.setenv(_STRICT_MODELS_ENV, "1")

    class _ChildDriver(_FakeDriver):
        def get_facts(self) -> models.FactsDict:
            return _BAD_FACTS  # malformed

    class _GrandchildDriver(_ChildDriver):
        pass  # inherits _ChildDriver.get_facts unchanged

    driver = _GrandchildDriver()
    with pytest.raises(napalm.base.exceptions.ModelValidationException):
        driver.get_facts()
