# Single-Factor Strategy

`single_factor` 策略把一个底层因子包装成可执行策略。

- 输入：市场面板中的 `close`、`volume`、`amount`
- 参数：`factor_kind`、`lookback`、`top_n`
- 输出：统一策略信号表

这个层级负责“策略如何组织因子”，而不是“因子本身如何计算”。
