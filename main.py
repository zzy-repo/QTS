#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from loguru import logger

from qts.core.analysis import equal_weight_benchmark
from qts.infra.config import (
    apply_overrides,
    default_qts_config,
    load_market_from_config,
    load_qts_config,
    save_qts_config,
)
from qts.infra.entrypoints import (
    DEFAULT_ENTRY_CONFIG,
    resolve_artifact_dir,
    resolve_entry_config_path,
    run_entry,
    save_entry_artifacts,
)
from qts.infra.logging_utils import configure_logging
from qts.infra.reporter import summarize_system_run

_ALLOCATION_LABELS = {"score": "打分", "equal": "等权", "risk_parity": "风险平价", "optimized": "优化组合"}
_OPTIMIZER_LABELS = {"score": "打分", "equal": "等权", "inv_vol": "逆波动率", "blend": "混合", "capped": "截断"}
_EXECUTION_LABELS = {"backtest": "回测", "sim": "模拟", "paper": "纸面"}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="QTS 正式统一入口")
    parser.add_argument(
        "--配置",
        "--config",
        dest="config_path",
        default=None,
        help=f"配置文件路径，默认读取 {DEFAULT_ENTRY_CONFIG}",
    )
    parser.add_argument(
        "--缓存目录",
        "--cache-root",
        dest="cache_root",
        default=None,
        help="覆盖行情缓存目录",
    )
    parser.add_argument(
        "--生成默认配置",
        "--write-default-config",
        dest="write_default_config",
        default=None,
        help="输出一份默认配置文件并退出",
    )
    parser.add_argument(
        "--调试摘要",
        "--summary-only",
        dest="summary_only",
        action="store_true",
        help="不落盘正式产物，只打印运行摘要，供临时调试使用",
    )
    parser.add_argument("--开始日期", "--start-date", dest="start_date", default=None, help="覆盖市场开始日期")
    parser.add_argument("--结束日期", "--end-date", dest="end_date", default=None, help="覆盖市场结束日期")
    parser.add_argument("--标的池", "--symbols", dest="symbols", nargs="+", default=None, help="覆盖标的池")
    parser.add_argument("--初始资金", "--initial-cash", dest="initial_cash", type=float, default=None, help="覆盖初始资金")
    parser.add_argument("--手数", "--lot-size", dest="lot_size", type=int, default=None, help="覆盖最小交易单位")
    parser.add_argument("--分配器", "--allocator", dest="allocation_mode", default=None, help="覆盖分配器模式")
    parser.add_argument("--优化器", "--optimizer", dest="optimizer_mode", default=None, help="覆盖优化器模式")
    parser.add_argument("--执行器", "--executor", dest="execution_mode", default=None, help="覆盖执行器模式")
    return parser


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


def main() -> None:
    args = _build_parser().parse_args()

    if args.write_default_config:
        target = Path(args.write_default_config)
        save_qts_config(default_qts_config(), target)
        print(f"已写出默认配置：{target}")
        return

    cache_root = Path(args.cache_root) if args.cache_root else None
    resolved_config = resolve_entry_config_path(args.config_path)
    config = load_qts_config(resolved_config)
    config = apply_overrides(
        config,
        start_date=args.start_date,
        end_date=args.end_date,
        symbols=args.symbols,
        initial_cash=args.initial_cash,
        lot_size=args.lot_size,
        allocation_mode=args.allocation_mode,
        optimizer_mode=args.optimizer_mode,
        execution_mode=args.execution_mode,
    )

    if args.summary_only:
        market = load_market_from_config(config, cache_root=cache_root)
        from qts.infra.config import build_system_from_config

        system = build_system_from_config(config)
        result = system.run(market)
        benchmark = equal_weight_benchmark(market.close) if not market.close.empty else None
        summary = summarize_system_run(result, benchmark=benchmark)
        _print_run_summary(system, result, summary)
        return

    artifact_dir = resolve_artifact_dir(config)
    log_path = configure_logging(config.entry.name, artifact_dir)
    logger.info("正式入口启动 输出目录={} 日志路径={} 配置路径={}", artifact_dir, log_path, resolved_config or DEFAULT_ENTRY_CONFIG)
    run = run_entry(config_path=resolved_config, cache_root=cache_root)
    save_entry_artifacts(run)
    logger.info("正式入口完成 入口={} 配置路径={}", run.name, run.config_path or DEFAULT_ENTRY_CONFIG)
    print(f"正式入口已完成: {run.name}")


if __name__ == "__main__":
    main()
