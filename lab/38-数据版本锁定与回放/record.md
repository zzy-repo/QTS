# 38-数据版本锁定与回放

- 目标：验证数据快照可锁定并用于复现。
- 状态：pass

## 过程记录

- 把行情快照写出并对 close / volume 做 hash。
- 重新加载同一区间数据，检查版本指纹是否一致。

## 产物

- artifacts/close.csv
- artifacts/volume.csv
- artifacts/snapshot.json

## 结论

- 数据版本锁定后可重复回放。
