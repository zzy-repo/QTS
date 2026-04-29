# Blend Optimizer

`blend_weight_optimizer` 在得分权重和倒波动率权重之间做线性混合。

## 输入

- `signals`: 至少包含 `date`、`symbol`、`score`、`volatility` 的信号表。
- `score_weight`: 得分权重分量，默认 `0.5`。

## 输出

返回统一目标权重表，字段包括：

- `date`
- `symbol`
- `weight`
- `optimizer`

## 说明

- `score_weight` 越大，结果越接近 score optimizer。
- 如果任一分量在某日退化为零和，会回退为等权分量。
