# 21-组合数值稳定性

- 目标：验证协方差矩阵在近奇异场景下可通过收缩保持稳定。
- 状态：pass

## 过程记录

- 构造近共线收益矩阵，制造协方差近奇异场景。
- 对协方差矩阵做对角收缩并比较条件数和最小特征值。
- 面板来源：offline-seed。

## 产物

- artifacts/raw_cov.csv
- artifacts/shrunk_cov.csv
- artifacts/weights.csv
- artifacts/summary.csv

## 结论

- 收缩后矩阵更稳定，权重集中度得到抑制。
