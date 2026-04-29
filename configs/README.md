# Configs

集中存放统一入口 `main.py` 使用的 profile 配置。

- `qts.config.json`：默认配置
- `backtest.json`：回测 profile
- `close_report.json`：收盘决策 profile
- `stock_selection.json`：选股 profile

每份配置都可通过 `入口` 段声明：

- `名称`
- `报表类型`
- `输出目录`
- `输出内容`
