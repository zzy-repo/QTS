# 33-订单生命周期与异步撮合

- 目标：验证订单可以按 NEW / PARTIAL / FILLED / CANCEL 流转。
- 状态：pass

## 过程记录

- 对满额、部分成交和取消三种订单分别生成生命周期事件。
- 把订单状态落成事件表，验证状态机可追踪。
- 面板来源：offline-seed。

## 产物

- artifacts/order_lifecycle.csv

## 结论

- 订单生命周期可追踪，撮合结果可被状态机表达。
