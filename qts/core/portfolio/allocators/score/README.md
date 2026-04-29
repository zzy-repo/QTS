# Score Allocator

`score_allocate_capital` 根据每个策略在最新一期信号中的 `score` 聚合结果分配资金。

## 输入

- `strategy_signals`: 至少包含 `date`、`strategy`、`score` 的信号表。
- `total_cash`: 可分配总资金。
- `caps`: 可选的单策略权重上限。
- `context`: 可选分配上下文；当前实现不使用该参数。

## 输出

返回 `AllocationResult`，包含：

- `allocation`: 每个策略对应的 `allocated_cash`
- `cash_left`: 因上限约束未能分配出去的现金

## 说明

- 仅使用最新一个交易日的策略信号参与资金分配。
- 默认按各策略 `score` 绝对值之和归一化分配。
- 当全部策略得分为零时，回退为等权分配。
- 当设置 `caps` 时，超出上限的资金不会强行分配，而是保留为 `cash_left`。
