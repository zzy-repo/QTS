# 36-多策略资本分配

- 目标：验证 strategy -> allocator -> executor 的中间分层。
- 状态：pass

## 过程记录

- 把两种策略信号合并，再交给独立 allocator 分配资金。
- 验证策略层和资金分配层之间有清晰边界。
- 面板来源：offline-seed。

## 产物

- artifacts/strategy_signals.csv
- artifacts/allocation.csv

## 结论

- 多策略资本分配层可独立工作。
