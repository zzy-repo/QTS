# 05-数据源可达性

- 目标：分析数据源不可达是出在环境代理、DNS、TCP/TLS，还是请求层。
- 状态：pass

## 过程记录

- 采样当前代理相关环境变量。
- 解析目标主机 push2his.eastmoney.com 的 DNS。
- 直接建立到 push2his.eastmoney.com:443 的 TCP 连接。
- 在 TCP 基础上执行 TLS 握手。
- 分别用 httpx 在 trust_env=False 和 trust_env=True 下访问目标请求。

## 产物

- artifacts/probe.md

## 结论

- 目标源本身可达，问题更像出在 AkShare 的请求链路或其内部网络栈，而不是数据源不可达。
