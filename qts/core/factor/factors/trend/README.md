# Trend Factor

`trend_follow_signal` 同时使用短周期和长周期收益率，构造趋势跟随打分。

## 输入

- `close`: 收盘价矩阵。
- `amount`: 可选成交额矩阵。
- `lookback`: 主回看周期。
- `top_n`: 每期输出标的数量。

## 输出

输出统一信号表，包含：

- `date`
- `symbol`
- `rank`
- `score`
- `weight`
- `volatility`
- `adv`

## 说明

- 短周期收益率使用 `max(2, lookback // 2)`。
- `score` 为短周期和长周期收益率的等权平均。
- `weight` 按得分绝对值归一化。
