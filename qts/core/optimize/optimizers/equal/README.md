# Equal Optimizer

`equal_weight_optimizer` 对每个调仓日的入选标的做等权分配。

## 输入

- `signals`: 至少包含 `date`、`symbol` 的信号表。

## 输出

返回统一目标权重表，字段包括：

- `date`
- `symbol`
- `weight`
- `optimizer`

## 说明

- 每个交易日内所有标的权重相同。
- 空输入会返回带标准列名的空表。
