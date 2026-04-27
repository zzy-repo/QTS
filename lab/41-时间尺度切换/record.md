# 41-时间尺度切换

- 目标：验证日频到 tick-like 尺度切换只影响数据层和参数层。
- 状态：pass

## 过程记录

- 把同一策略分别跑在日频和 tick-like 数据上。
- 只调整数据层和 lookback 参数，不改策略函数或执行器。
- 面板来源：offline-seed。

## 产物

- artifacts/daily_signals.csv
- artifacts/tick_signals.csv
- artifacts/daily_pnl.csv
- artifacts/tick_pnl.csv

## 结论

- 时间尺度切换只影响数据和参数层。
