# Trend Factor

`trend_follow_signal` 同时使用短周期和长周期收益率，生成全横截面趋势跟随分数。

## 输入

- `close`: 收盘价矩阵。
- `amount`: 可选成交额矩阵。
- `lookback`: 主回看周期。
- `top_n`: 由上层策略使用的保留参数，因子层本身不截断输出。

## 输出

输出统一信号表，包含：

- `date`
- `symbol`
- `rank`
- `score`
- `volatility`
- `adv`

## 说明

- 短周期收益率使用 `max(2, lookback // 2)`。
- `score` 为短周期和长周期收益率的等权平均。
