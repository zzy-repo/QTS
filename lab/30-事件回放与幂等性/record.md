# 30-事件回放与幂等性

- 目标：验证订单事件可回放，并且重复回放结果一致。
- 状态：pass

## 过程记录

- 把订单和成交结果写成事件序列，再按顺序回放。
- 重复回放两次，检查幂等性和最终权益一致性。
- 面板来源：offline-seed。

## 产物

- artifacts/orders.csv
- artifacts/holdings.csv
- artifacts/pnl.csv
- artifacts/replay_a.csv
- artifacts/replay_b.csv

## 结论

- 事件可以回放，重复执行结果一致。
