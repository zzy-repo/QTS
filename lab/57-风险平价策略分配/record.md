# 57-风险平价策略分配

- 目标：验证策略层资金可依据策略收益协方差做风险平价分配。
- 状态：pass

## 过程记录

- 从策略日收益面板估计近 60 期协方差矩阵，并做轻度对角收缩。
- 通过迭代法求解 long-only 风险平价权重。
- 检查各策略风险贡献是否收敛到近似相等。
- 面板来源：offline-seed。

## 产物

- artifacts/strategy_returns.csv
- artifacts/covariance.csv
- artifacts/allocation.csv

## 结论

- 风险平价分配可解，策略间风险贡献已收敛到接近均衡。
