# Inverse Vol Optimizer

`inverse_vol_optimizer` 按波动率倒数分配目标权重。

## 输入

- `signals`: 至少包含 `date`、`symbol`、`volatility` 的信号表。

## 输出

返回统一目标权重表，字段包括：

- `date`
- `symbol`
- `weight`
- `optimizer`

## 说明

- 权重按 `1 / volatility` 归一化。
- 若某日有效倒数波动率全为零，则回退为等权。
