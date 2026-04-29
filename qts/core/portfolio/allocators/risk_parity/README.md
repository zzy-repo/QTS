# Risk Parity Allocator

`risk_parity_allocate_capital` 根据最新一期策略信号聚合出的策略波动率，做 long-only 风险平价资金分配。

## 输入

- `strategy_signals`: 至少包含 `date`、`strategy`，并建议包含 `weight`、`volatility` 的信号表。
- `total_cash`: 可分配总资金。
- `caps`: 可选的单策略权重上限。
- `context`: 可选分配上下文；当提供 `market` 或 `strategy_return_history` 时，会优先使用历史策略收益协方差。

## 输出

返回 `AllocationResult`，包含：

- `allocation`: 每个策略对应的 `allocated_cash`
- `cash_left`: 因上限约束未能分配出去的现金

## 说明

- 仅使用最新一个交易日的策略信号参与资金分配。
- 当 `context` 提供历史策略收益时，优先基于历史收益协方差做风险平价分配。
- 当缺少历史收益上下文时，回退为按策略内目标权重聚合资产波动率，再构造策略级对角协方差矩阵。
- 默认通过迭代法求解 long-only 风险平价权重，使各策略风险贡献尽量接近。
- 当缺少有效 `volatility` 时，会使用样本中位数做回填，避免分配器失效。
- 当设置 `caps` 时，超出上限的资金不会强行分配，而是保留为 `cash_left`。
