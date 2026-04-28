# 53-回测入口报错溯源

- 目标：隔离当前回测入口的失败链路，确认是默认回退关闭还是行情接口网络异常导致报错。
- 状态：pass

## 过程记录

- 读取当前回测配置，确认默认 `allow_synthetic_fallback` 为 false。
- 在相同配置下直接调用 `load_market_panel`，捕获当前失败类型和完整 traceback。
- 将相同配置切换为显式允许 synthetic 回退，验证流程可恢复并返回 offline-seed 面板。

## 产物

- artifacts/config_probe.json
- artifacts/error_probe.json
- artifacts/fallback_probe.json
- artifacts/traceback.txt

## 结论

- 当前报错来自行情接口的网络层断连；默认不允许合成回退时，入口会直接暴露该异常。
