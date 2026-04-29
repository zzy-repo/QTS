# QTS 量化系统

一个可扩展的多决策量化系统。`lab/` 保留为工程可行性实验层，`qts/` 现在分成 `core/` 和 `infra/` 两层。

运行统一正式入口：

```bash
uv run python main.py --config-name close_report
```

运行不同 profile：

```bash
uv run python main.py --config-name backtest
uv run python main.py --config-name close_report
uv run python main.py --config-name stock_selection
```

使用默认配置并通过 Hydra 覆盖字段：

```bash
uv run python main.py market.start_date=20240115 runtime.summary_only=true
```

三个入口各自也可使用独立配置：

- `configs/backtest.yaml`
- `configs/close_report.yaml`
- `configs/stock_selection.yaml`

生成一份默认 YAML 配置：

```bash
uv run python main.py --write-default-config configs/qts.yaml
```

约定：

- `main.py` 是正式统一入口，负责 profile 化运行与产物落盘。
- `runtime.summary_only=true` 用于临时调试摘要，不落正式产物。

策略配置统一使用英文 YAML schema。示例：

```yaml
strategies:
  - name: core_blend
    strategy_kind: factor
    factor_kinds: [momentum, trend, sharpe]
    factor_weights:
      momentum: 0.4
      trend: 0.3
      sharpe: 0.3
    lookback: 20
    top_n: 3
```

行情数据默认会缓存到 `.cache/qts-market/`，供不同正式入口共享复用；可通过 `QTS_MARKET_CACHE_DIR` 覆盖。

各配置文件的 `entry` 段定义报表类型、输出目录和产物列表。`artifacts/backtest/`、`artifacts/close_report/`、`artifacts/stock_selection/`、`artifacts/qts/` 仅保存各 profile 的结果、日志和摘要，不再承载行情缓存。
