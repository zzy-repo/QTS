# 11-组合构建闭环

- 目标：从“选股”过渡到“组合”。
- 状态：pass

## 过程记录

- 实现等权和波动率倒数加权两种组合方式。
- 面板来源：offline-seed。
- 输出每日权重分布并检查权重归一性。
- 对比权重是否出现异常集中或负值。

## 产物

- artifacts/weights_equal.csv
- artifacts/weights_inv_vol.csv
- artifacts/weight_summary.csv

## 结论

- 权重归一，未见异常集中或负值。
