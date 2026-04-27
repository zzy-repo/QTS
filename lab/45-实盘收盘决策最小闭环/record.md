# 45-实盘收盘决策最小闭环

- 目标：验证收盘后数据装配、信号生成、建议单、执行、风控和调度是否能形成最小闭环。
- 状态：pass

## 过程记录

- 用中文字段的原始日线样本做标准化和质量校验。
- 把多标的日线样本装配成 MarketPanel，再跑单日动量信号和目标权重。
- 把目标权重转成建议单，并用 backtest / paper 两种执行方式对比滑点影响。
- 对权益曲线注入回撤冲击，验证风控状态机和建议单门控。
- 按收盘后日级调度连续触发 5 次，检查任务可重复执行。

## 产物

- artifacts/raw.csv
- artifacts/normalized.csv
- artifacts/market_snapshot.csv
- artifacts/signals.csv
- artifacts/backtest_orders.csv
- artifacts/backtest_pnl.csv
- artifacts/paper_orders.csv
- artifacts/paper_pnl.csv
- artifacts/risk_state.csv
- artifacts/advice.csv
- artifacts/schedule_log.csv

## 结论

- A-F 最小闭环已打通。
