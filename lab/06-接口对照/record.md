# 06-接口对照

- 目标：对照 AkShare 封装和原生请求，确认接口本身是否正确。
- 状态：pass

## 过程记录

- 调用 AkShare 的 stock_zh_a_hist。
- 用原生 requests.get 访问同一条东财历史行情接口。
- 用 requests.Session(trust_env=False) 再访问同一接口。

## 产物

- artifacts/probe.md

## 结论

- 接口本身是同一条东财 kline 接口；AkShare 失败而原生请求成功时，问题更可能在封装或环境继承。
