from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import narwhals.stable.v1 as nw
from tests.utils import compare_dicts

data = [1, 2, 3]


def test_to_list(constructor_eager: Any) -> None:
    s = nw.from_native(constructor_eager({"a": data}), eager_only=True)["a"]

    assert isinstance(s, Iterable)
    compare_dicts({"a": [x for x in s]}, {"a": [1, 2, 3]})  # noqa: C416
