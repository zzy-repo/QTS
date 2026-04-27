# 31-策略层解耦

- 目标：验证策略只做输入到目标权重的纯变换。
- 状态：pass

## 过程记录

- 把行情输入封装为 StrategyInput，只让策略返回信号与权重。
- 重复调用同一策略，检查输出是否稳定。
- 面板来源：offline-seed。

## 产物

- artifacts/momentum.csv
- artifacts/trend.csv

## 结论

- 策略层只做纯函数变换，未触碰资金或执行状态。
