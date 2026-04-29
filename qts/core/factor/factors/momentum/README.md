# Momentum Factor

`momentum_signal` 按回看区间收益率生成全横截面动量分数。

## 输入

- `close`: 收盘价矩阵，行为时间，列为标的。
- `amount`: 可选成交额矩阵，用于计算 `adv`。
- `lookback`: 动量回看窗口。
- `top_n`: 由上层策略使用的保留参数，因子层本身不截断输出。

## 输出

输出统一因子分数表，包含以下字段：

- `date`
- `symbol`
- `rank`
- `score`
- `volatility`
- `adv`

## 说明

- `score` 为 `lookback` 周期收益率。
- `volatility` 为基于日收益率的滚动波动率。
