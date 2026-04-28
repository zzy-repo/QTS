from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import json
import sys
import traceback

ROOT = Path(__file__).resolve().parent
LAB_ROOT = ROOT.parent
REPO_ROOT = LAB_ROOT.parent
sys.path.insert(0, str(LAB_ROOT))
sys.path.insert(0, str(REPO_ROOT))

from qts.core.data.data_source import load_market_panel
from qts.infra.config import load_qts_config
from qts.infra.entrypoints import DEFAULT_BACKTEST_CONFIG
from shared import ExperimentMeta, record_experiment


def _probe_default_config() -> dict[str, object]:
    config = load_qts_config(DEFAULT_BACKTEST_CONFIG)
    return {
        "config_path": str(DEFAULT_BACKTEST_CONFIG),
        "symbols": list(config.market.symbols),
        "start_date": config.market.start_date,
        "end_date": config.market.end_date,
        "allow_synthetic_fallback": config.market.allow_synthetic_fallback,
        "execution_mode": config.system.execution_mode,
        "optimizer_mode": config.system.optimizer_mode,
    }


def _capture_load_error(config) -> dict[str, object]:
    try:
        load_market_panel(
            config.market.symbols,
            config.market.start_date,
            config.market.end_date,
            allow_synthetic_fallback=config.market.allow_synthetic_fallback,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "traceback": "".join(traceback.format_exception(exc)),
        }
    return {
        "error_type": None,
        "error_message": None,
        "traceback": None,
    }


def _capture_fallback_probe(config) -> dict[str, object]:
    fallback_config = replace(config, market=replace(config.market, allow_synthetic_fallback=True))
    market = load_market_panel(
        fallback_config.market.symbols,
        fallback_config.market.start_date,
        fallback_config.market.end_date,
        allow_synthetic_fallback=fallback_config.market.allow_synthetic_fallback,
    )
    return {
        "market_source_mode": market.source_mode,
        "close_rows": int(len(market.close)),
        "volume_rows": int(len(market.volume)),
        "amount_rows": int(len(market.amount)),
    }


def main() -> None:
    meta = ExperimentMeta(
        code="53",
        title="回测入口报错溯源",
        goal="隔离当前回测入口的失败链路，确认是默认回退关闭还是行情接口网络异常导致报错。",
        root=ROOT,
    )

    artifact_dir = ROOT / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    config = load_qts_config(DEFAULT_BACKTEST_CONFIG)
    config_probe = _probe_default_config()
    error_probe = _capture_load_error(config)
    fallback_probe = _capture_fallback_probe(config)

    (artifact_dir / "config_probe.json").write_text(json.dumps(config_probe, ensure_ascii=False, indent=2), encoding="utf-8")
    (artifact_dir / "error_probe.json").write_text(json.dumps(error_probe, ensure_ascii=False, indent=2), encoding="utf-8")
    (artifact_dir / "fallback_probe.json").write_text(json.dumps(fallback_probe, ensure_ascii=False, indent=2), encoding="utf-8")
    if error_probe["traceback"]:
        (artifact_dir / "traceback.txt").write_text(error_probe["traceback"], encoding="utf-8")

    steps = [
        "读取当前回测配置，确认默认 `allow_synthetic_fallback` 为 false。",
        "在相同配置下直接调用 `load_market_panel`，捕获当前失败类型和完整 traceback。",
        "将相同配置切换为显式允许 synthetic 回退，验证流程可恢复并返回 offline-seed 面板。",
    ]
    artifacts = [
        "artifacts/config_probe.json",
        "artifacts/error_probe.json",
        "artifacts/fallback_probe.json",
        "artifacts/traceback.txt",
    ]

    if error_probe["error_type"] == "RemoteProtocolError" and fallback_probe["market_source_mode"] == "offline-seed":
        status = "pass"
        conclusion = "当前报错来自行情接口的网络层断连；默认不允许合成回退时，入口会直接暴露该异常。"
    else:
        status = "fail"
        conclusion = "未能稳定复现或隔离当前回测入口的失败原因。"

    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
