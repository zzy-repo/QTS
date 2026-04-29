# Momentum Factor

`momentum_signal` 按回看区间收益率对标的排序，并选取得分最高的 `top_n` 个标的。

## 输入

- `close`: 收盘价矩阵，行为时间，列为标的。
- `amount`: 可选成交额矩阵，用于计算 `adv`。
- `lookback`: 动量回看窗口。
- `top_n`: 每期保留的标的数量。

## 输出

输出统一信号表，包含以下字段：

- `date`
- `symbol`
- `rank`
- `score`
- `weight`
- `volatility`
- `adv`

## 说明

- `score` 为 `lookback` 周期收益率。
- `weight` 采用等权分配。
- `volatility` 为基于日收益率的滚动波动率。
