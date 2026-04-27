# 22-调仓频率与成本

- 目标：验证较低调仓频率可压缩换手和交易成本。
- 状态：pass

## 过程记录

- 对同一策略分别采用日频和周频子采样调仓。
- 比较总换手和成本，检查频率下降后是否收敛。
- 面板来源：offline-seed。

## 产物

- artifacts/daily_pnl.csv
- artifacts/weekly_pnl.csv
- artifacts/daily_costed.csv
- artifacts/weekly_costed.csv

## 结论

- 调仓频率下降后，换手和成本同步下降。
