# 46-入口隔离与标准化

- 目标：验证同一核心模块可被不同入口复用，且输出格式、配置和缓存接口可以统一。
- 状态：pass

## 过程记录

- 三个最小入口分别调用同一套 qts.config、qts.engine、qts.data_source。
- 统一把信号整理成 date/symbol/rank/score/weight 五列，再交给 report.py。
- 用独立配置文件区分回测、收盘决策和选股参数。
- 用 sync_symbol_history 的自定义缓存回调验证首次拉取与二次命中复用。

## 产物

- artifacts/backtest_signals.csv
- artifacts/backtest_pnl.csv
- artifacts/backtest_report.csv
- artifacts/close_signals.csv
- artifacts/close_report.csv
- artifacts/selection_signals.csv
- artifacts/selection_report.csv
- artifacts/entry_summary.csv
- artifacts/cache_probe.json

## 结论

- 入口可以隔离，信号可以标准化，配置和缓存也能按入口独立复用。
