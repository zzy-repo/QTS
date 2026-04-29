# Sharpe Factor

`sharpe_signal` 基于滚动 Sharpe 排序，并叠加流动性、点差代理和市值代理约束。

## 输入

- `close`: 收盘价矩阵。
- `amount`: 可选成交额矩阵。
- `lookback`: 统计窗口。
- `top_n`: 每期保留数量。

## 输出

输出统一信号表，包含：

- `date`
- `symbol`
- `rank`
- `score`
- `weight`
- `volatility`
- `adv`
- `cap_proxy`
- `spread_proxy`

## 说明

- `score` 为滚动均值除以滚动波动率得到的 Sharpe 代理。
- `adv`、`cap_proxy`、`spread_proxy` 用于横截面过滤。
- 如果过滤后为空，则回退为原始 Sharpe 排名前 `top_n`。
