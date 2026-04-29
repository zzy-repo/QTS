#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import hydra
from loguru import logger
from omegaconf import DictConfig, OmegaConf

from qts.core.analysis import equal_weight_benchmark
from qts.infra.config import build_system_from_config, config_from_mapping, default_qts_config, load_market_from_config, save_qts_config
from qts.infra.entrypoints import _run_loaded_config, _save_entry_artifacts, resolve_artifact_dir
from qts.infra.logging_utils import configure_logging
from qts.infra.reporter import summarize_system_run

_ALLOCATION_LABELS = {"score": "打分", "equal": "等权", "risk_parity": "风险平价", "optimized": "优化组合"}
_OPTIMIZER_LABELS = {"score": "打分", "equal": "等权", "inv_vol": "逆波动率", "blend": "混合", "capped": "截断"}
_EXECUTION_LABELS = {"backtest": "回测", "sim": "模拟", "paper": "纸面"}


def _preparse_cli() -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--write-default-config", dest="write_default_config", default=None)
    args, _ = parser.parse_known_args()
    return args


def _print_run_summary(system, result, summary) -> None:
    print("QTS 调试摘要")
    print(
        f"分配模式={_ALLOCATION_LABELS.get(system.allocation_mode, system.allocation_mode)} "
        f"执行模式={_EXECUTION_LABELS.get(system.execution_mode, system.execution_mode)} "
        f"优化模式={_OPTIMIZER_LABELS.get(system.optimizer_mode, system.optimizer_mode)}"
    )
    print(f"策略数={len(system.strategies)} 分配行数={len(result.allocation.allocation)}")
    aggregate_row = summary.loc[summary["strategy"].eq("aggregate")].iloc[0] if not summary.empty else None
    final_equity = float(result.aggregate_equity["equity"].iloc[-1]) if not result.aggregate_equity.empty else 0.0
    annualized_return = float(aggregate_row["annualized_return"]) if aggregate_row is not None else float("nan")
    print(f"汇总最终权益={final_equity:.2f} 汇总年化收益={annualized_return:.2%}")
    print(summary.to_string(index=False))


@hydra.main(version_base=None, config_path="configs", config_name="qts")
def hydra_main(cfg: DictConfig) -> None:
    config = config_from_mapping(OmegaConf.to_container(cfg, resolve=True), source="hydra")
    cache_root = Path(config.runtime.cache_root) if config.runtime.cache_root else None
    if config.runtime.summary_only:
        market = load_market_from_config(config, cache_root=cache_root)
        system = build_system_from_config(config)
        result = system.run(market)
        benchmark = equal_weight_benchmark(market.close) if not market.close.empty else None
        summary = summarize_system_run(result, benchmark=benchmark)
        _print_run_summary(system, result, summary)
        return

    artifact_dir = resolve_artifact_dir(config)
    log_path = configure_logging(config.entry.name, artifact_dir)
    logger.info("正式入口启动 输出目录={} 日志路径={}", artifact_dir, log_path)
    run = _run_loaded_config(config, config_path=None, cache_root=cache_root)
    _save_entry_artifacts(run)
    logger.info("正式入口完成 入口={}", run.name)
    print(f"正式入口已完成: {run.name}")


def main() -> None:
    args = _preparse_cli()
    if args.write_default_config:
        target = Path(args.write_default_config)
        save_qts_config(default_qts_config(), target)
        print(f"已写出默认配置：{target}")
        return
    hydra_main()


if __name__ == "__main__":
    main()
