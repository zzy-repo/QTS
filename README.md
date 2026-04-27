# QTS 量化系统

一个可扩展的多决策量化系统。`lab/` 保留为工程可行性实验层，`qts/` 是正式系统层。

运行 demo：

```bash
.venv/bin/python main.py
```

使用中文配置文件：

```bash
.venv/bin/python main.py --配置 qts.config.json
```

生成一份默认中文配置：

```bash
.venv/bin/python main.py --生成默认配置 qts.config.json
```

行情数据默认会缓存到 `.cache/qts-market/`，可通过 `QTS_MARKET_CACHE_DIR` 覆盖。
