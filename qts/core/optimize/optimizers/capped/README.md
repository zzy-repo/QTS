# Capped Optimizer

`capped_optimizer` 先按 score optimizer 生成权重，再施加单标的权重上限。

## 输入

- `signals`: 至少包含 `date`、`symbol`、`score` 的信号表。
- `cap`: 单标的权重上限，默认 `0.4`。

## 输出

返回统一目标权重表，字段包括：

- `date`
- `symbol`
- `weight`
- `optimizer`

## 说明

- 截断后会在每个交易日内重新归一化。
- 当前实现是一次截断再归一化，不做多轮水位再分配。
