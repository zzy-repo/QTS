# 27-T加1限制与涨跌停成交

- 目标：验证 T+1 和涨跌停会约束成交，而不是无条件成交。
- 状态：pass

## 过程记录

- 用 T+1 记账表模拟同日买入后立即卖出被阻断。
- 在真实调仓执行中加入不可交易 mask，模拟涨跌停/停牌无法成交。
- 面板来源：offline-seed。

## 产物

- artifacts/orders.csv
- artifacts/holdings.csv
- artifacts/pnl.csv
- artifacts/t1_log.csv

## 结论

- T+1、涨跌停和最小交易单位都能约束成交。
