# 12-风险指标闭环

- 目标：建立策略评价能力。
- 状态：pass

## 过程记录

- 基于成本后收益序列计算 Sharpe、最大回撤和波动率。
- 面板来源：offline-seed。
- 检查指标是否随策略变化而变化。
- 验证指标数值是否稳定且无 NaN/异常值。

## 产物

- artifacts/metrics.csv
- artifacts/equity.csv

## 结论

- 风险指标数值稳定，可用于策略评价。
