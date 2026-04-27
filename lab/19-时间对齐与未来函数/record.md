# 19-时间对齐与未来函数

- 目标：验证信号、成交价、持仓和收益严格按时间顺序对齐。
- 状态：pass

## 过程记录

- 用过去 20 日收益生成信号，并把成交和收益顺延到后续交易日。
- 构造一个未来函数负样本，把 trade_date 人为回写到 signal_date。
- 面板来源：offline-seed。

## 产物

- artifacts/alignment.csv
- artifacts/bad_alignment.csv

## 结论

- 时间链路满足严格顺序，未来函数样本可被审计发现。
