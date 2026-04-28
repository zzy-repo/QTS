# 54-东财接口市场码校验

- 目标：对照 AkShare 源码，确认历史行情接口是否被错误地固定为深市市场码。
- 状态：pass

## 过程记录

- 读取当前实现的 `fetch_daily_history` 请求模板，检查 `secid` 拼接方式。
- 读取 AkShare 的 `stock_zh_a_hist` 源码，确认历史行情函数如何构造同一接口。
- 对 000001、600519、601318 计算期望 `secid`，核对沪市与深市市场码是否一致。

## 产物

- artifacts/current_request.json
- artifacts/akshare_request.json
- artifacts/expected_secid.json

## 结论

- 接口 URL 本身是对的，但当前实现把 secid 固定成 0.*，而 AkShare 会按股票代码前缀切换市场码；600519/601318 应该用 1.*。
