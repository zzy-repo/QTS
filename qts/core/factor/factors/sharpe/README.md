# Sharpe Factor

`sharpe_signal` 基于滚动 Sharpe 排序，并叠加流动性、点差代理和市值代理约束，输出可用横截面。

## 输入

- `close`: 收盘价矩阵。
- `amount`: 可选成交额矩阵。
- `lookback`: 统计窗口。
- `top_n`: 由上层策略使用的保留参数，因子层本身不截断输出。

## 输出

输出统一信号表，包含：

- `date`
- `symbol`
- `rank`
- `score`
- `volatility`
- `adv`
- `cap_proxy`
- `spread_proxy`

## 说明

- `score` 为滚动均值除以滚动波动率得到的 Sharpe 代理。
- `adv`、`cap_proxy`、`spread_proxy` 用于横截面过滤。
- 如果过滤后为空，则回退为原始 Sharpe 横截面。
