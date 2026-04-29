# Equal Allocator

`equal_allocate_capital` 根据最新一期出现的策略集合做等权资金分配。

## 输入

- `strategy_signals`: 至少包含 `date`、`strategy` 的信号表。
- `total_cash`: 可分配总资金。
- `caps`: 可选的单策略权重上限。
- `context`: 可选分配上下文；当前实现不使用该参数。

## 输出

返回 `AllocationResult`，包含：

- `allocation`: 每个策略对应的 `allocated_cash`
- `cash_left`: 因上限约束未能分配出去的现金

## 说明

- 仅使用最新一个交易日的策略信号参与资金分配。
- 默认按最新交易日出现的策略数量做等权切分。
- 不依赖 `score` 强弱，策略层只要存在有效信号就参与平均分配。
- 当设置 `caps` 时，超出上限的资金不会强行分配，而是保留为 `cash_left`。
