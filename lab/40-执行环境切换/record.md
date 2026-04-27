# 40-执行环境切换

- 目标：验证回测、模拟和近实盘执行可以通过同一适配器接口切换。
- 状态：pass

## 过程记录

- 保持策略和优化器不变，只切换执行适配器。
- 对比回测、模拟和近实盘三种执行环境的输出。
- 面板来源：offline-seed。

## 产物

- artifacts/backtest_pnl.csv
- artifacts/sim_pnl.csv
- artifacts/paper_pnl.csv

## 结论

- 执行环境可以通过适配器切换，其余模块不需要改动。
