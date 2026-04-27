from __future__ import annotations

from pathlib import Path
import hashlib
import json
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parent
LAB_ROOT = ROOT.parent
sys.path.insert(0, str(LAB_ROOT))

from shared import DEFAULT_UNIVERSE, ExperimentMeta, load_market_panel, record_experiment, save_csv


def _fingerprint(df: pd.DataFrame) -> str:
    payload = df.to_csv(index=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def main() -> None:
    meta = ExperimentMeta(
        code="38",
        title="数据版本锁定与回放",
        goal="验证数据快照可锁定并用于复现。",
        root=ROOT,
    )
    market = load_market_panel(DEFAULT_UNIVERSE, "20240102", "20240315")
    close = market.close.copy()
    version = {
        "source_mode": market.source_mode,
        "start": str(close.index.min().date()),
        "end": str(close.index.max().date()),
        "close_hash": _fingerprint(close),
        "volume_hash": _fingerprint(market.volume),
    }

    artifact_dir = ROOT / "artifacts"
    save_csv(close.reset_index(), artifact_dir / "close.csv")
    save_csv(market.volume.reset_index(), artifact_dir / "volume.csv")
    (artifact_dir / "snapshot.json").write_text(json.dumps(version, ensure_ascii=False, indent=2), encoding="utf-8")

    replay_market = load_market_panel(DEFAULT_UNIVERSE, "20240102", "20240315")
    replay_version = {
        "source_mode": replay_market.source_mode,
        "start": str(replay_market.close.index.min().date()),
        "end": str(replay_market.close.index.max().date()),
        "close_hash": _fingerprint(replay_market.close),
        "volume_hash": _fingerprint(replay_market.volume),
    }

    stable = version == replay_version
    steps = [
        "把行情快照写出并对 close / volume 做 hash。",
        "重新加载同一区间数据，检查版本指纹是否一致。",
    ]
    artifacts = ["artifacts/close.csv", "artifacts/volume.csv", "artifacts/snapshot.json"]
    if stable:
        status = "pass"
        conclusion = "数据版本锁定后可重复回放。"
    else:
        status = "fail"
        conclusion = "数据版本指纹未保持一致。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
