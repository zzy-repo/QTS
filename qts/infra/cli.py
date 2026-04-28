from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from .config import (
    apply_overrides,
    default_qts_config,
    load_qts_config,
    save_qts_config,
)
from .models import QTSConfig
from .reporter import summarize_system_run

_OPTIMIZER_LABELS = {"score": "打分", "equal": "等权", "capped": "截断"}
_EXECUTION_LABELS = {"backtest": "回测", "sim": "模拟", "paper": "纸面"}


def _build_parser() -> argparse.ArgumentParser:
    """构建命令行解析器。"""
    parser = argparse.ArgumentParser(description="QTS 多决策系统演示")
    parser.add_argument(
        "--配置",
        "--config",
        dest="config_path",
        default=None,
        help="配置文件路径，默认读取 configs/qts.config.json",
    )
    parser.add_argument(
        "--生成默认配置",
        "--write-default-config",
        dest="write_default_config",
        default=None,
        help="输出一份中文友好的默认配置文件并退出",
    )
    parser.add_argument("--开始日期", "--start-date", dest="start_date", default=None, help="覆盖市场开始日期")
    parser.add_argument("--结束日期", "--end-date", dest="end_date", default=None, help="覆盖市场结束日期")
    parser.add_argument(
        "--标的池",
        "--symbols",
        dest="symbols",
        nargs="+",
        default=None,
        help="覆盖标的池，例如 --标的池 000001 600519 601318",
    )
    parser.add_argument("--初始资金", "--initial-cash", dest="initial_cash", type=float, default=None, help="覆盖初始资金")
    parser.add_argument("--手数", "--lot-size", dest="lot_size", type=int, default=None, help="覆盖最小交易单位")
    parser.add_argument("--优化器", "--optimizer", dest="optimizer_mode", default=None, help="覆盖优化器模式")
    parser.add_argument("--执行器", "--executor", dest="execution_mode", default=None, help="覆盖执行器模式")
    return parser


def _print_run_summary(system, result, summary) -> None:
    """打印系统运行摘要。"""
    print("QTS 多决策系统演示")
    print(
        f"执行模式={_EXECUTION_LABELS.get(system.execution_mode, system.execution_mode)} "
        f"优化模式={_OPTIMIZER_LABELS.get(system.optimizer_mode, system.optimizer_mode)}"
    )
    print(f"策略数={len(system.strategies)} 分配行数={len(result.allocation.allocation)}")
    aggregate_row = summary.loc[summary["strategy"].eq("aggregate")].iloc[0] if not summary.empty else None
    final_equity = float(result.aggregate_equity["equity"].iloc[-1]) if not result.aggregate_equity.empty else 0.0
    annualized_return = float(aggregate_row["annualized_return"]) if aggregate_row is not None else float("nan")
    print(f"汇总最终权益={final_equity:.2f} 汇总年化收益={annualized_return:.2%}")
    print(summary.to_string(index=False))


def run_cli(argv: Sequence[str] | None = None) -> None:
    """运行命令行入口。"""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.write_default_config:
        target = Path(args.write_default_config)
        save_qts_config(default_qts_config(), target)
        print(f"已写出默认配置：{target}")
        return

    config = load_qts_config(args.config_path)
    config = apply_overrides(
        config,
        start_date=args.start_date,
        end_date=args.end_date,
        symbols=args.symbols,
        initial_cash=args.initial_cash,
        lot_size=args.lot_size,
        optimizer_mode=args.optimizer_mode,
        execution_mode=args.execution_mode,
    )
    market, system, result, summary = run_demo_from_config(config)
    _print_run_summary(system, result, summary)


def run_demo_from_config(config: QTSConfig):
    """按配置运行一次 demo。"""
    from .config import build_system_from_config, load_market_from_config

    market = load_market_from_config(config)
    system = build_system_from_config(config)
    result = system.run(market)
    summary = summarize_system_run(result)
    return market, system, result, summary


if __name__ == "__main__":
    run_cli()
