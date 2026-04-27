# QTS Files

## qts/__init__.py

系统级导出入口。

## qts/models.py

系统通用数据结构定义。

## qts/data_source.py

行情数据获取、标准化、质量检查与离线回退。

## qts/config.py

中文友好的配置模型、加载、保存与系统组装。

## qts/strategy.py

策略纯函数输出与策略结果校验。

## qts/optimization.py

目标权重优化与回退策略。

## qts/allocation.py

多策略资本分配。

## qts/execution.py

执行适配、部分成交、滑点和成交约束。

## qts/diagnostics.py

风险状态判断。

## qts/resilience.py

执行适配器、时间尺度扩展与指纹工具。

## qts/engine.py

多决策系统编排。

## qts/presets.py

默认策略与默认系统组装。

## qts/cli.py

命令行 demo 入口。

## configs/qts.config.json

默认中文配置样例。

## configs/backtest.json

回测入口配置样例。

## configs/close_report.json

收盘决策入口配置样例。

## configs/stock_selection.json

选股入口配置样例。
