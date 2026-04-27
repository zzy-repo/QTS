from __future__ import annotations

from .presets import run_demo


def main() -> None:
    market, system, result, summary = run_demo()
    print("QTS 多决策系统演示")
    print(f"执行模式={system.execution_mode} 优化模式={system.optimizer_mode}")
    print(f"策略数={len(system.strategies)} 分配行数={len(result.allocation.allocation)}")
    print(f"汇总最终权益={float(result.aggregate_equity['equity'].iloc[-1]) if not result.aggregate_equity.empty else 0.0:.2f}")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
