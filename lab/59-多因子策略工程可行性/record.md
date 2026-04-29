# 59-多因子策略工程可行性

- 目标：验证在不修改主干代码的前提下，能否以实验方式把多个单因子组合成一个可执行策略。
- 状态：pass

## 过程记录

- 在实验目录内实现一个多因子 builder，把多个单因子信号合成为统一策略输出。
- 直接复用现有 StrategySpec、SignalGenerator 和 MultiDecisionSystem，验证下游流水线无需改动即可运行。
- 组合因子：momentum, trend, sharpe；权重：{'momentum': 0.4, 'trend': 0.3, 'sharpe': 0.3}；行情来源：offline-seed。
- 额外统计候选覆盖率，检查当前因子接口是否只暴露 top_n 结果，从而限制多因子在策略层做完整横截面融合。

## 产物

- artifacts/multi_factor_signal.csv
- artifacts/generated_signals.csv
- artifacts/coverage_summary.csv
- artifacts/strategy_run_summary.csv
- artifacts/aggregate_pnl.csv
- artifacts/feasibility_summary.csv

## 结论

- 多因子策略在工程上可通过自定义 builder 接入现有流水线，但当前因子层只输出入选 top_n，限制了策略层做完整横截面融合。
