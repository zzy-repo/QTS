# QTS 量化系统

一个可扩展的多决策量化系统。`lab/` 保留为工程可行性实验层，`qts/` 现在分成 `core/` 和 `infra/` 两层。

运行统一正式入口：

```bash
.venv/bin/python main.py --config configs/close_report.json
```

运行不同 profile：

```bash
.venv/bin/python main.py --config configs/backtest.json
.venv/bin/python main.py --config configs/close_report.json
.venv/bin/python main.py --config configs/stock_selection.json
```

使用中文配置文件：

```bash
.venv/bin/python main.py --配置 configs/qts.config.json
```

三个入口各自也可使用独立配置：

- `configs/backtest.json`
- `configs/close_report.json`
- `configs/stock_selection.json`

生成一份默认中文配置：

```bash
.venv/bin/python main.py --write-default-config configs/qts.config.json
```

约定：

- `main.py` 是正式统一入口，负责 profile 化运行与产物落盘。
- `main.py --summary-only` 用于临时调试摘要，不落正式产物。

策略配置统一使用 `因子列表`，可选 `因子权重`。单因子也写成单元素列表，例如：

```json
{
  "名称": "core_blend",
  "策略类型": "因子策略",
  "因子列表": ["动量", "趋势", "夏普"],
  "因子权重": {"动量": 0.4, "趋势": 0.3, "夏普": 0.3},
  "回看周期": 20,
  "选取数量": 3
}
```

行情数据默认会缓存到 `.cache/qts-market/`，供不同正式入口共享复用；可通过 `QTS_MARKET_CACHE_DIR` 覆盖。

各配置文件的 `入口` 段定义报表类型、输出目录和产物列表。`artifacts/backtest/`、`artifacts/close_report/`、`artifacts/stock_selection/`、`artifacts/qts/` 仅保存各 profile 的结果、日志和摘要，不再承载行情缓存。
