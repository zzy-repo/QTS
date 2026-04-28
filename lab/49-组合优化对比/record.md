# 49-组合优化对比

- 目标：比较权重组合、流动性约束、交易成本和再平衡频率对组合表现的影响。
- 状态：pass

## 过程记录

- 构造 Sharpe、逆波动率和 50/50 混合三种权重方案。
- 以不同 max_adv_pct 测试流动性约束强弱。
- 对手续费做 2/5/10 bps 敏感性分析。
- 对日/周/半月再平衡频率做子采样比较。
- 面板来源：offline-seed。

## 产物

- artifacts/scheme_compare.csv
- artifacts/liquidity_compare.csv
- artifacts/cost_sensitivity.csv
- artifacts/rebalance_frequency.csv

## 结论

- 混合权重、流动性约束、成本和频率对比均呈现预期方向。
