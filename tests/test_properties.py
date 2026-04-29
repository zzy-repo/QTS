from __future__ import annotations

import math

import pandas as pd
from hypothesis import given, strategies as st

from qts.core.portfolio.allocators.common import finalize_allocation
from qts.core.strategy.validators import validate_strategy_output


@st.composite
def signal_frames(draw):
    day_count = draw(st.integers(min_value=1, max_value=4))
    symbol_count = draw(st.integers(min_value=1, max_value=5))
    dates = pd.bdate_range("2024-01-02", periods=day_count).strftime("%Y-%m-%d").tolist()
    symbols = [f"{index:06d}" for index in range(1, symbol_count + 1)]

    rows: list[dict[str, object]] = []
    for date in dates:
        raw_weights = draw(
            st.lists(
                st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
                min_size=symbol_count,
                max_size=symbol_count,
            )
        )
        total = sum(raw_weights)
        normalized = [1.0 / symbol_count] * symbol_count if total <= 0 else [value / total for value in raw_weights]
        for rank, (symbol, weight) in enumerate(zip(symbols, normalized, strict=True), start=1):
            score = draw(st.floats(min_value=-100.0, max_value=100.0, allow_nan=False, allow_infinity=False))
            rows.append(
                {
                    "date": date,
                    "symbol": symbol,
                    "rank": rank,
                    "score": score,
                    "weight": weight,
                }
            )
    return pd.DataFrame(rows)


@st.composite
def allocation_inputs(draw):
    strategy_count = draw(st.integers(min_value=1, max_value=6))
    names = [f"s{index}" for index in range(strategy_count)]
    raw_weights = draw(
        st.lists(
            st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
            min_size=strategy_count,
            max_size=strategy_count,
        )
    )
    total = sum(raw_weights)
    weights = [1.0 / strategy_count] * strategy_count if total <= 0 else [value / total for value in raw_weights]
    caps = draw(
        st.one_of(
            st.none(),
            st.dictionaries(
                st.sampled_from(names),
                st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
                min_size=1,
                max_size=strategy_count,
            ),
        )
    )
    total_cash = draw(st.floats(min_value=1.0, max_value=1_000_000.0, allow_nan=False, allow_infinity=False))
    return pd.Series(weights, index=names, dtype=float), caps, total_cash


@given(signal_frames())
def test_validate_strategy_output_accepts_finite_normalized_weights(frame: pd.DataFrame) -> None:
    issues = validate_strategy_output(frame)
    assert issues == []


@given(allocation_inputs())
def test_finalize_allocation_preserves_budget_and_caps(payload) -> None:
    weights, caps, total_cash = payload

    result = finalize_allocation(weights, total_cash=total_cash, caps=caps)

    assert result.cash_left >= -1e-8
    assert (result.allocation["allocated_cash"] >= -1e-8).all()

    allocated = float(result.allocation["allocated_cash"].sum())
    assert math.isclose(allocated + result.cash_left, float(total_cash), rel_tol=1e-8, abs_tol=1e-6)

    if caps:
        allocation_map = result.allocation.set_index("strategy")["allocated_cash"]
        for strategy, cap in caps.items():
            if strategy in allocation_map:
                assert float(allocation_map[strategy]) <= float(total_cash) * float(cap) + 1e-6
