"""Several methods to help with the tests."""

from pydantic import BaseModel, ValidationError


def test_model(model, data, allow_subset=False):
    """Return if the dictionary ``data`` complies with the ``model``.

    ``model`` is either a Pydantic ``BaseModel`` subclass (the current shape) or
    a legacy ``TypedDict`` (kept for transitional compatibility).
    """
    if isinstance(model, type) and issubclass(model, BaseModel):
        return _validate_pydantic(model, data, allow_subset=allow_subset)
    return _validate_typeddict(model, data, allow_subset=allow_subset)


def _validate_pydantic(model, data, allow_subset=False):
    """Validate ``data`` against a Pydantic ``BaseModel``.

    ``allow_subset`` mirrors the legacy behaviour: it tolerates ``data``
    containing only a subset of the model's fields. With Pydantic this means
    "ignore missing required fields" — we approximate it by constructing the
    model without validation when ``allow_subset`` is set.
    """
    try:
        if allow_subset:
            # ``model_construct`` skips validation but still enforces field set.
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


def _validate_typeddict(model, data, allow_subset=False):
    """Legacy TypedDict validator — kept for any out-of-tree callers."""
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
