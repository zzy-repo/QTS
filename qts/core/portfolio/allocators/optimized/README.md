# Optimized Allocator

`optimized_allocate_capital` 根据最新一期策略信号聚合出的策略得分和波动率，做基于信号代理的 long-only 优化组合资金分配。

## 输入

- `strategy_signals`: 至少包含 `date`、`strategy`、`score`，并建议包含 `weight`、`volatility` 的信号表。
- `total_cash`: 可分配总资金。
- `caps`: 可选的单策略权重上限。
- `context`: 可选分配上下文；当提供 `market` 或 `strategy_return_history` 时，会优先使用历史策略收益估计 `mu` 和 `Sigma`。

## 输出

返回 `AllocationResult`，包含：

- `allocation`: 每个策略对应的 `allocated_cash`
- `cash_left`: 因上限约束未能分配出去的现金

## 说明

- 仅使用最新一个交易日的策略信号参与资金分配。
- 当 `context` 提供历史策略收益时，优先使用历史策略收益估计 `mu` 和 `Sigma`。
- 当缺少历史收益上下文时，回退为把各策略 `score` 绝对值之和归一化为收益代理，再按聚合波动率构造策略级对角协方差矩阵。
- 默认在 long-only 约束下比较优化解、最小方差解和等权解，并选择效用最高的候选权重。
- 当全部策略得分为零时，收益代理回退为等权。
- 当设置 `caps` 时，超出上限的资金不会强行分配，而是保留为 `cash_left`。
