# 24-动态Universe与幸存者偏差

- 目标：验证 universe 按周期滚动筛选，而不是静态过滤。
- 状态：pass

## 过程记录

- 按过去 20 日收益和流动性排序，每个交易日重新筛选 universe。
- 统计被选入的标的频次，检查是否存在静态幸存者偏差。
- 面板来源：offline-seed。

## 产物

- artifacts/universe_history.csv
- artifacts/symbol_frequency.csv
- artifacts/daily_count.csv

## 结论

- universe 是滚动更新的，选择结果会随时间变化。
