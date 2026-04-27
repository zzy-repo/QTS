# 18-数据一致性与污染

- 目标：验证缺失、重复和异常值可被识别，并且填充后可恢复。
- 状态：pass

## 过程记录

- 基于同一面板生成标准 OHLCV 结构。
- 注入重复日期、负价格、异常高低点和负成交量。
- 对缺失值执行前向填充后再次校验。
- 面板来源：offline-seed。

## 产物

- artifacts/clean.csv
- artifacts/polluted.csv
- artifacts/filled.csv

## 结论

- 数据污染可识别，缺失填充后可恢复到可用状态。
