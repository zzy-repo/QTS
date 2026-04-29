# 55-东财断连与腾讯替代链路

- 目标：在 lab 中复现东财历史接口断连，并验证腾讯历史日线能否在相同配置下替代并跑通最小回测链路。
- 状态：pass

## 过程记录

- 读取当前 `configs/backtest.yaml`，沿用真实的标的池和日期窗口做复现。
- 直接请求东财历史接口，记录当前网络环境下的失败类型和请求参数。
- 把同一组股票代码映射成腾讯市场前缀代码，调用 `ak.stock_zh_a_hist_tx` 下载历史日线。
- 将腾讯日线整理成 `MarketPanel` 结构，并在 lab 中调用现有系统跑最小回测。

## 产物

- artifacts/eastmoney_probe.json
- artifacts/tx_probe.json
- artifacts/tx_history.csv
- artifacts/tx_close_panel.csv
- artifacts/summary.md

## 结论

- 当前环境下东财历史接口在连接层断开；腾讯历史日线可在相同配置下完成取数并跑通最小回测链路，说明问题主要在数据源访问路径而不在回测内核。
