# 20-部分成交与盘口约束

- 目标：验证成交量约束会触发部分成交，而不是虚假满额成交。
- 状态：pass

## 过程记录

- 以较宽和较紧的 ADV 约束分别执行同一组调仓指令。
- 比较平均填充率和剩余权重误差，观察部分成交是否发生。
- 面板来源：offline-seed。

## 产物

- artifacts/relaxed_orders.csv
- artifacts/relaxed_holdings.csv
- artifacts/constrained_orders.csv
- artifacts/constrained_holdings.csv

## 结论

- 成交量约束触发了部分成交，未出现虚假满额成交。
