# QTS 量化系统

一个可扩展的多决策量化系统。`lab/` 保留为工程可行性实验层，`qts/` 现在分成 `core/` 和 `infra/` 两层。

运行 demo：

```bash
.venv/bin/python -m qts.cli
```

运行收盘决策入口：

```bash
.venv/bin/python scripts/close.py
```

运行正式入口：

```bash
.venv/bin/python scripts/backtest.py
.venv/bin/python scripts/close_report.py
.venv/bin/python scripts/stock_selection.py
```

使用中文配置文件：

```bash
.venv/bin/python -m qts.cli --配置 configs/qts.config.json
```

三个入口各自也可使用独立配置：

- `configs/backtest.json`
- `configs/close_report.json`
- `configs/stock_selection.json`

生成一份默认中文配置：

```bash
.venv/bin/python -m qts.cli --write-default-config configs/qts.config.json
```

行情数据默认会缓存到 `.cache/qts-market/`，供不同正式入口共享复用；可通过 `QTS_MARKET_CACHE_DIR` 覆盖。

`artifacts/backtest/`、`artifacts/close_report/`、`artifacts/stock_selection/` 仅保存各入口自己的结果、日志和摘要，不再承载行情缓存。
