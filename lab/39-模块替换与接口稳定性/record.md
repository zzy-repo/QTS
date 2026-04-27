# 39-模块替换与接口稳定性

- 目标：验证核心模块替换时上层编排无需改动。
- 状态：pass

## 过程记录

- 保持同一编排函数不变，只替换 optimizer 模块。
- 用两个不同 optimizer 输出同一份上层目标权重接口。
- 面板来源：offline-seed。

## 产物

- artifacts/equal_optimizer.csv
- artifacts/score_optimizer.csv
- artifacts/equal_pnl.csv
- artifacts/score_pnl.csv

## 结论

- 核心模块可替换，上层只需要改 wiring。
