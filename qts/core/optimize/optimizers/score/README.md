# Score Optimizer

`score_weight_optimizer` 按每个标的信号得分绝对值分配目标权重。

## 输入

- `signals`: 至少包含 `date`、`symbol`、`score` 的信号表。

## 输出

返回统一目标权重表，字段包括：

- `date`
- `symbol`
- `weight`
- `optimizer`

## 说明

- 权重按 `abs(score)` 归一化。
- 如果某日全部得分为零，则回退为等权。
