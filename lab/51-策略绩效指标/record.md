# 51-策略绩效指标

- 目标：补齐完整绩效指标、滚动绩效和成本敏感性结果。
- 状态：pass

## 过程记录

- 基于同一策略收益序列，补齐 Sharpe、MDD、Sortino、Beta、Alpha、Skew、Kurtosis、Turnover、WinRate 等指标。
- 分别按 21 日和 63 日窗口计算滚动绩效。
- 对交易成本做 0/2/5/10 bps 敏感性分析。
- 面板来源：offline-seed。

## 产物

- artifacts/metrics.csv
- artifacts/rolling_metrics.csv
- artifacts/sensitivity.csv

## 结论

- 完整绩效指标与滚动绩效均可稳定输出，成本变化也能拉开差异。
