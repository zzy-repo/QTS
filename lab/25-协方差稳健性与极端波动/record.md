# 25-协方差稳健性与极端波动

- 目标：验证缺失值和极端波动可通过 winsorize 与 shrinkage 缓释。
- 状态：pass

## 过程记录

- 注入缺失值和极端波动，制造不稳定收益矩阵。
- 先做填充，再做 winsorize，最后对协方差做收缩。
- 面板来源：offline-seed。

## 产物

- artifacts/filled_returns.csv
- artifacts/winsorized_returns.csv
- artifacts/raw_cov.csv
- artifacts/shrunk_cov.csv

## 结论

- 极端波动和缺失值可被稳健化流程压住，协方差矩阵可继续用于下游。
