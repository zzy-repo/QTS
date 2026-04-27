# 13-调仓执行闭环

- 目标：打通「目标权重 → 实际成交」。
- 状态：pass

## 过程记录

- 按每日目标权重生成买卖数量。
- 面板来源：offline-seed。
- 记录 135 条调仓指令和 135 条持仓变化。
- 最大权重偏差 0.000757。

## 产物

- artifacts/orders.csv
- artifacts/holdings.csv
- artifacts/pnl.csv

## 结论

- 持仓可正确收敛到目标权重，误差在可接受范围内。
