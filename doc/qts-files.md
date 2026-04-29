# QTS Files

## qts/
- `qts/__init__.py`: 系统级聚合导出入口。

## qts/core/
- `qts/core/`: 算法核心层，负责交易决策、执行与组合管理。
- `qts/core/data/models.py`: 核心数据结构定义。
- `qts/core/data/data_source.py`: 行情数据获取、标准化、质量检查与离线回退。
- `qts/core/signal/strategy.py`: 策略纯函数输出与策略结果校验。
- `qts/core/signal/engine.py`: 信号生成编排。
- `qts/core/signal/specs.py`: 策略入口规范定义。
- `qts/core/optimize/optimization.py`: 目标权重优化与回退策略。
- `qts/core/optimize/engine.py`: 优化器门面。
- `qts/core/execution/execution.py`: 执行、滑点和成交约束。
- `qts/core/execution/engine.py`: 执行器门面。
- `qts/core/portfolio/allocation.py`: 多策略资本分配。
- `qts/core/portfolio/results.py`: 系统运行结果与收益年化工具。
- `qts/core/portfolio/resilience.py`: 执行适配器、时间尺度扩展与指纹工具。
- `qts/core/portfolio/engine.py`: 组合管理与结果汇总。

## qts/infra/
- `qts/infra/`: 基础设施层，负责配置、入口、报表和诊断。
- `qts/infra/models.py`: Pydantic 配置模型与入口数据模型。
- `qts/infra/config.py`: YAML 配置加载、保存与系统组装。
- `qts/infra/system.py`: 系统编排与多决策系统门面。
- `qts/infra/report.py`: 统一报表与信号规范。
- `qts/infra/diagnostics.py`: 风险状态判断。
- `qts/infra/reporter.py`: 系统结果汇总报表。
- `qts/infra/entrypoints.py`: 正式统一入口编排与产物落盘。

## configs/
- `configs/`: 正式系统配置样例。
- `configs/qts.yaml`: 默认配置样例。
- `configs/backtest.yaml`: 回测入口配置样例。
- `configs/close_report.yaml`: 收盘决策入口配置样例。
- `configs/stock_selection.yaml`: 选股入口配置样例。
