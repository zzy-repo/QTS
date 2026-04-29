# 56-等权策略分配

- 目标：验证策略层资金可按等权方式稳定分配，并与策略信号强弱隔离。
- 状态：pass

## 过程记录

- 从同一市场面板构造 momentum、trend、defensive 三组策略信号与下一日收益。
- 仅使用策略集合，不读取 score 强弱，直接按策略个数做等权分配。
- 面板来源：offline-seed。

## 产物

- artifacts/strategy_signals.csv
- artifacts/strategy_returns.csv
- artifacts/allocation.csv

## 结论

- 等权分配可独立工作，策略强弱不会影响策略层资金切分。
