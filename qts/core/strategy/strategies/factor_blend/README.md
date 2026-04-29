# Factor Blend Strategy

`build_factor_strategy` 把一个或多个底层因子组合成可执行策略。

## 输入

- `factor_kinds`: 因子名称列表。
- `factor_weights`: 因子权重字典，未提供时默认等权。
- `lookback`: 策略回看窗口。
- `top_n`: 每期最终保留的标的数量。

## 行为

- 因子层先输出全横截面分数。
- 策略层对每个因子按日期做 z-score 标准化，再按权重求和。
- 策略层统一完成最终排序、选股和权重分配。

## 输出

输出统一策略信号表，包含：

- `date`
- `symbol`
- `rank`
- `score`
- `weight`
- `factor_hits`

以及可供下游优化器和执行器使用的市场特征列，例如 `volatility`、`adv`。
