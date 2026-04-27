# 14-滑点模型闭环

- 目标：引入更真实的成交价格偏移。
- 状态：pass

## 过程记录

- 基于成交额和波动率建模动态滑点。
- 面板来源：offline-seed。
- 对比小额与大额资金场景下的滑点成本。
- 小额滑点 983.20，大额滑点 11936.38。

## 产物

- artifacts/small.csv
- artifacts/large.csv
- artifacts/slippage_compare.csv

## 结论

- 滑点随成交规模变化，大额交易成本显著高于小额交易。
