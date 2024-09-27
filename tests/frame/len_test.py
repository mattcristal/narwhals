from typing import Any

import narwhals.stable.v1 as nw

data = {
    "a": [1.0, 2.0, None, 4.0],
    "b": [None, 3.0, None, 5.0],
}


def test_len(constructor_eager: Any) -> None:
    result = len(nw.from_native(constructor_eager(data), eager_only=True))
    assert result == 4
