# 58-优化组合策略分配

- 目标：验证策略层资金可依据预期收益和协方差做长仓优化组合分配。
- 状态：pass

## 过程记录

- 从近 60 期策略收益估计预期收益与协方差。
- 求解 long-only 均值方差候选权重，并与最小方差、等权候选做效用比较。
- 输出最优候选模式：optimized。
- 面板来源：offline-seed。

## 产物

- artifacts/strategy_returns.csv
- artifacts/expected_returns.csv
- artifacts/allocation.csv
- artifacts/objective_compare.csv

## 结论

- 优化组合分配可解，样本内效用不弱于等权和风险平价基线。
