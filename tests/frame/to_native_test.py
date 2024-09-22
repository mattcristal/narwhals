from typing import Any

import narwhals.stable.v1 as nw


def test_to_native(constructor: Any) -> None:
    data = {"a": [1, 3, 2], "b": [4, 4, 6], "z": [7.1, 8, 9]}
    df_raw = constructor(data)
    df = nw.from_native(df_raw)

    assert isinstance(df.to_native(), df_raw.__class__)
