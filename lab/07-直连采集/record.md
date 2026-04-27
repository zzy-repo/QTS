# 07-直连采集

- 目标：验证同一东财接口在 httpx 直连下是否可以稳定采集历史行情。
- 状态：pass

## 过程记录

- 使用与 AkShare 相同的东财 kline 接口。
- 改用 httpx.Client(trust_env=False) 直接请求并解析 JSON。
- 将返回的 kline 切分并整理为标准字段。
- 成功采集 11 行历史行情。

## 产物

- artifacts/history.csv

## 结论

- 同一接口在 httpx 直连下可用，说明可继续沿这条链路做数据获取。
