from __future__ import annotations

from contextlib import nullcontext
from typing import Any

import pandas as pd
import polars as pl
import pyarrow as pa
import pytest

import narwhals.stable.v1 as nw
from narwhals.utils import parse_version
from tests.utils import Constructor
from tests.utils import compare_dicts

data = {"a": [1, 1, 3], "b": [4, 4, 6], "c": [7.0, 8, 9]}

df_pandas = pd.DataFrame(data)
df_lazy = pl.LazyFrame(data)


def test_group_by_complex() -> None:
    expected = {"a": [1, 3], "b": [-3.5, -3.0]}

    df = nw.from_native(df_pandas)
    with pytest.warns(UserWarning, match="complex group-by"):
        result = nw.to_native(
            df.group_by("a").agg((nw.col("b") - nw.col("c").mean()).mean()).sort("a")
        )
    compare_dicts(result, expected)

    lf = nw.from_native(df_lazy).lazy()
    result = nw.to_native(
        lf.group_by("a").agg((nw.col("b") - nw.col("c").mean()).mean()).sort("a")
    )
    compare_dicts(result, expected)


def test_invalid_group_by_dask() -> None:
    pytest.importorskip("dask")
    pytest.importorskip("dask_expr", exc_type=ImportError)
    import dask.dataframe as dd

    df_dask = dd.from_pandas(df_pandas)

    with pytest.raises(ValueError, match=r"Non-trivial complex found"):
        nw.from_native(df_dask).group_by("a").agg(nw.col("b").mean().min())

    with pytest.raises(RuntimeError, match="does your"):
        nw.from_native(df_dask).group_by("a").agg(nw.col("b"))

    with pytest.raises(
        ValueError, match=r"Anonymous expressions are not supported in group_by\.agg"
    ):
        nw.from_native(df_dask).group_by("a").agg(nw.all().mean())


def test_invalid_group_by() -> None:
    df = nw.from_native(df_pandas)
    with pytest.raises(RuntimeError, match="does your"):
        df.group_by("a").agg(nw.col("b"))
    with pytest.raises(
        ValueError, match=r"Anonymous expressions are not supported in group_by\.agg"
    ):
        df.group_by("a").agg(nw.all().mean())
    with pytest.raises(
        ValueError, match=r"Anonymous expressions are not supported in group_by\.agg"
    ):
        nw.from_native(pa.table({"a": [1, 2, 3]})).group_by("a").agg(nw.all().mean())
    with pytest.raises(ValueError, match=r"Non-trivial complex found"):
        nw.from_native(pa.table({"a": [1, 2, 3]})).group_by("a").agg(
            nw.col("b").mean().min()
        )


def test_group_by_iter(constructor_eager: Any) -> None:
    df = nw.from_native(constructor_eager(data), eager_only=True)
    expected_keys = [(1,), (3,)]
    keys = []
    for key, sub_df in df.group_by("a"):
        if key == (1,):
            expected = {"a": [1, 1], "b": [4, 4], "c": [7.0, 8.0]}
            compare_dicts(sub_df, expected)
            assert isinstance(sub_df, nw.DataFrame)
        keys.append(key)
    assert sorted(keys) == sorted(expected_keys)
    expected_keys = [(1, 4), (3, 6)]  # type: ignore[list-item]
    keys = []
    for key, _ in df.group_by("a", "b"):
        keys.append(key)
    assert sorted(keys) == sorted(expected_keys)
    keys = []
    for key, _ in df.group_by(["a", "b"]):
        keys.append(key)
    assert sorted(keys) == sorted(expected_keys)


def test_group_by_len(constructor: Constructor) -> None:
    result = (
        nw.from_native(constructor(data)).group_by("a").agg(nw.col("b").len()).sort("a")
    )
    expected = {"a": [1, 3], "b": [2, 1]}
    compare_dicts(result, expected)


def test_group_by_n_unique(constructor: Constructor) -> None:
    result = (
        nw.from_native(constructor(data))
        .group_by("a")
        .agg(nw.col("b").n_unique())
        .sort("a")
    )
    expected = {"a": [1, 3], "b": [1, 1]}
    compare_dicts(result, expected)


def test_group_by_std(constructor: Constructor) -> None:
    data = {"a": [1, 1, 2, 2], "b": [5, 4, 3, 2]}
    result = (
        nw.from_native(constructor(data)).group_by("a").agg(nw.col("b").std()).sort("a")
    )
    expected = {"a": [1, 2], "b": [0.707107] * 2}
    compare_dicts(result, expected)


def test_group_by_n_unique_w_missing(
    constructor: Constructor, request: pytest.FixtureRequest
) -> None:
    if "cudf" in str(constructor):
        # Issue in cuDF https://github.com/rapidsai/cudf/issues/16861
        request.applymarker(pytest.mark.xfail)

    data = {"a": [1, 1, 2], "b": [4, None, 5], "c": [None, None, 7], "d": [1, 1, 3]}
    result = (
        nw.from_native(constructor(data))
        .group_by("a")
        .agg(
            nw.col("b").n_unique(),
            c_n_unique=nw.col("c").n_unique(),
            c_n_min=nw.col("b").min(),
            d_n_unique=nw.col("d").n_unique(),
        )
        .sort("a")
    )
    expected = {
        "a": [1, 2],
        "b": [2, 1],
        "c_n_unique": [1, 1],
        "c_n_min": [4, 5],
        "d_n_unique": [1, 1],
    }
    compare_dicts(result, expected)


def test_group_by_same_name_twice() -> None:
    import pandas as pd

    df = pd.DataFrame({"a": [1, 1, 2], "b": [4, 5, 6]})
    with pytest.raises(ValueError, match="two aggregations with the same"):
        nw.from_native(df).group_by("a").agg(nw.col("b").sum(), nw.col("b").n_unique())


def test_group_by_empty_result_pandas() -> None:
    df_any = pd.DataFrame({"a": [1, 2, 3], "b": [4, 3, 2]})
    df = nw.from_native(df_any, eager_only=True)
    with pytest.raises(ValueError, match="No results"):
        df.filter(nw.col("a") < 0).group_by("a").agg(
            nw.col("b").sum().round(2).alias("c")
        )


def test_group_by_simple_named(constructor: Constructor) -> None:
    data = {"a": [1, 1, 2], "b": [4, 5, 6], "c": [7, 2, 1]}
    df = nw.from_native(constructor(data)).lazy()
    result = (
        df.group_by("a")
        .agg(
            b_min=nw.col("b").min(),
            b_max=nw.col("b").max(),
        )
        .collect()
        .sort("a")
    )
    expected = {
        "a": [1, 2],
        "b_min": [4, 6],
        "b_max": [5, 6],
    }
    compare_dicts(result, expected)


def test_group_by_simple_unnamed(constructor: Constructor) -> None:
    data = {"a": [1, 1, 2], "b": [4, 5, 6], "c": [7, 2, 1]}
    df = nw.from_native(constructor(data)).lazy()
    result = (
        df.group_by("a")
        .agg(
            nw.col("b").min(),
            nw.col("c").max(),
        )
        .collect()
        .sort("a")
    )
    expected = {
        "a": [1, 2],
        "b": [4, 6],
        "c": [7, 1],
    }
    compare_dicts(result, expected)


def test_group_by_multiple_keys(constructor: Constructor) -> None:
    data = {"a": [1, 1, 2], "b": [4, 4, 6], "c": [7, 2, 1]}
    df = nw.from_native(constructor(data)).lazy()
    result = (
        df.group_by("a", "b")
        .agg(
            c_min=nw.col("c").min(),
            c_max=nw.col("c").max(),
        )
        .collect()
        .sort("a")
    )
    expected = {
        "a": [1, 2],
        "b": [4, 6],
        "c_min": [2, 1],
        "c_max": [7, 1],
    }
    compare_dicts(result, expected)


def test_key_with_nulls(constructor: Constructor, request: pytest.FixtureRequest) -> None:
    if "modin" in str(constructor):
        # TODO(unassigned): Modin flaky here?
        request.applymarker(pytest.mark.skip)
    context = (
        pytest.raises(NotImplementedError, match="null values")
        if (
            "pandas_constructor" in str(constructor)
            and parse_version(pd.__version__) < parse_version("1.0.0")
        )
        else nullcontext()
    )
    data = {"b": [4, 5, None], "a": [1, 2, 3]}
    with context:
        result = (
            nw.from_native(constructor(data))
            .group_by("b")
            .agg(nw.len(), nw.col("a").min())
            .sort("a")
            .with_columns(nw.col("b").cast(nw.Float64))
        )
        expected = {"b": [4.0, 5, float("nan")], "len": [1, 1, 1], "a": [1, 2, 3]}
        compare_dicts(result, expected)


def test_no_agg(constructor: Constructor) -> None:
    result = nw.from_native(constructor(data)).group_by(["a", "b"]).agg().sort("a", "b")

    expected = {"a": [1, 3], "b": [4, 6]}
    compare_dicts(result, expected)
