# 29-调仓触发与延迟执行

- 目标：验证调仓由信号触发，并且真正执行发生在下一根 bar。
- 状态：pass

## 过程记录

- 按 rolling signal 触发调仓，而不是每天固定执行。
- 把实际执行延迟到下一根 bar，避免同 bar 未来函数。
- 面板来源：offline-seed。

## 产物

- artifacts/trigger_log.csv
- artifacts/executed_log.csv

## 结论

- 调仓触发与延迟执行都能按信号驱动。
