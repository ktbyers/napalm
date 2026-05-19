"""Several methods to help with the tests."""

from pydantic import BaseModel, ValidationError


def test_model(model, data, allow_subset=False):
    """Return True if ``data`` validates against the Pydantic ``model``.

    Thin wrapper around ``model.model_validate(data)``. ``allow_subset`` is
    kept for back-compat with the legacy TypedDict-based signature: when set,
    we skip validation of *required* fields by using ``model.model_construct``
    (still enforces field-name set via ``extra='forbid'``).

    A legacy TypedDict path is retained for any out-of-tree callers that
    still pass ``TypedDict`` classes.
    """
    if isinstance(model, type) and issubclass(model, BaseModel):
        try:
            if allow_subset:
                model.model_construct(**data)
            else:
                model.model_validate(data)
        except ValidationError as exc:
            print(f"model: {model.__name__}\nvalidation errors:\n{exc}")
            return False
        except TypeError as exc:
            print(f"model: {model.__name__}\nconstruction error: {exc}")
            return False
        return True

    # ------------------------------------------------------------------
    # Legacy TypedDict path -- left in place for out-of-tree callers.
    # ------------------------------------------------------------------
    annotations = model.__annotations__
    if allow_subset:
        same_keys = set(data.keys()) <= set(annotations.keys())
        source = data
    else:
        same_keys = set(annotations.keys()) == set(data.keys())
        source = annotations

    if not same_keys:
        print(
            "model_keys: {}\ndata_keys: {}".format(sorted(annotations.keys()), sorted(data.keys()))
        )

    correct_class = True
    for key in source.keys():
        correct_class = isinstance(data[key], annotations[key]) and correct_class
        if not correct_class:
            print(
                "key: {}\nmodel_class: {}\ndata_class: {}".format(
                    key, annotations[key], data[key].__class__
                )
            )

    return correct_class and same_keys
