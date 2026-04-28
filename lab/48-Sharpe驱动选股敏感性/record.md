# 48-Sharpe驱动选股敏感性

- 目标：验证不同滚动窗口和流动性门槛下的 Sharpe 排序稳定性。
- 状态：pass

## 过程记录

- 用 rolling Sharpe 对标的排序，并在每个日期做流动性、价差和市值代理过滤。
- 分别测试 20/60/120 日窗口，观察候选集变化是否明显。
- 统计连续日期的 overlap 和 turnover，检查信号稳定性。
- 面板来源：offline-seed。

## 产物

- artifacts/selection_history.csv
- artifacts/stability_metrics.csv
- artifacts/scenario_summary.csv

## 结论

- Sharpe 选股对窗口和流动性门槛敏感，信号稳定性可量化。
