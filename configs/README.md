# Configs

集中存放统一入口 `main.py` 使用的 profile 配置。

- `qts.yaml`：默认配置
- `backtest.yaml`：回测 profile
- `close_report.yaml`：收盘决策 profile
- `stock_selection.yaml`：选股 profile

每份配置都可通过 `entry` 段声明：

- `name`
- `report_kind`
- `artifact_dir`
- `outputs`
