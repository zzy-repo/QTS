# 17-结果持久化闭环

- 目标：保证策略结果可追溯。
- 状态：pass

## 过程记录

- 落盘持仓、交易、PnL、指标四类结果。
- 面板来源：offline-seed。
- 从磁盘回放并校验历史状态是否一致。

## 产物

- artifacts/orders.csv
- artifacts/holdings.csv
- artifacts/pnl.csv
- artifacts/metrics.csv
- artifacts/manifest.txt

## 结论

- 数据完整、无缺失、可复算。
