# 02-失败恢复

- 目标：验证采集过程在超时后能否重试并在成功后继续落盘。
- 状态：pass

## 过程记录

- 构造一个前两次请求必然超时、第三次成功的源包装器。
- 每次失败都写入当前重试次数作为断点信息。
- 第 1 次请求失败并写入断点：simulated timeout on attempt 1
- 第 2 次请求失败并写入断点：simulated timeout on attempt 2
- 第 3 次请求成功并完成落盘。

## 产物

- artifacts/checkpoint.txt
- artifacts/recovered.csv

## 结论

- 重试与断点记录机制可工作，失败后可恢复到成功落盘。
