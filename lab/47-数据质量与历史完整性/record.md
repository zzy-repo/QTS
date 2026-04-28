# 47-数据质量与历史完整性

- 目标：检验缺失值处理方式与历史数据覆盖率是否满足下游实验需要。
- 状态：pass

## 过程记录

- 将每个标的的 OHLCV 数据单独做缺失值注入，构造污染样本。
- 对比 dropna、前向/后向填充和中位数填充三种恢复方式。
- 按业务日历统计历史覆盖率，检查是否存在明显缺口。
- 面板来源：offline-seed。

## 产物

- artifacts/polluted_sample.csv
- artifacts/quality_sensitivity.csv
- artifacts/historical_completeness.csv

## 结论

- 缺失值可通过填充恢复，历史覆盖率也满足连续性要求。
