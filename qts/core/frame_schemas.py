from __future__ import annotations

import pandas as pd
import pandera.pandas as pa
from pandera import Check
from pandera.pandas import Column
from pandera.errors import SchemaErrors


def _datetime_like(series: pd.Series) -> bool:
    return pd.to_datetime(series, format="mixed", errors="coerce").notna().all()


SIGNAL_SCHEMA = pa.DataFrameSchema(
    {
        "date": Column(object, checks=Check(_datetime_like, error="date must be parseable as datetime")),
        "symbol": Column(str, checks=Check.str_length(min_value=1)),
        "rank": Column(float, checks=Check.ge(1), coerce=True),
        "score": Column(float, nullable=False, coerce=True),
        "weight": Column(float, checks=Check.ge(0), nullable=False, coerce=True),
    },
    strict=False,
    coerce=True,
)

TARGET_SCHEMA = pa.DataFrameSchema(
    {
        "date": Column(object, checks=Check(_datetime_like, error="date must be parseable as datetime")),
        "symbol": Column(str, checks=Check.str_length(min_value=1)),
        "weight": Column(float, checks=Check.ge(0), nullable=False, coerce=True),
    },
    strict=False,
    coerce=True,
)

PNL_SCHEMA = pa.DataFrameSchema(
    {
        "date": Column(object, checks=Check(_datetime_like, error="date must be parseable as datetime")),
        "signal_date": Column(object, checks=Check(_datetime_like, error="signal_date must be parseable as datetime")),
        "gross_return": Column(float, nullable=False, coerce=True),
    },
    strict=False,
    coerce=True,
)

HISTORY_SCHEMA = pa.DataFrameSchema(
    {
        "date": Column(object, checks=Check(_datetime_like, error="date must be parseable as datetime")),
        "symbol": Column(str, checks=Check.str_length(min_value=1)),
        "close": Column(float, checks=Check.gt(0), nullable=False, coerce=True),
        "volume": Column(float, checks=Check.ge(0), nullable=True, coerce=True),
        "amount": Column(float, checks=Check.ge(0), nullable=True, coerce=True),
        "provider": Column(str, checks=Check.str_length(min_value=1)),
    },
    strict=False,
    coerce=True,
)


def collect_schema_issues(exc: SchemaErrors) -> list[str]:
    """Convert pandera failure cases into readable messages."""
    if exc.failure_cases is None or exc.failure_cases.empty:
        return [str(exc)]
    issues: list[str] = []
    for _, row in exc.failure_cases.iterrows():
        column = row.get("column", "<schema>")
        check = row.get("check", "schema validation failed")
        failure = row.get("failure_case", "")
        issues.append(f"{column}: {check} ({failure})")
    return issues
