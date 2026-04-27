from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


LAB_ROOT = Path(__file__).resolve().parents[1]
SUMMARY_PATH = LAB_ROOT / "records.md"


@dataclass(frozen=True)
class ExperimentMeta:
    code: str
    title: str
    goal: str
    root: Path

    @property
    def slug(self) -> str:
        return f"{self.code}-{self.title}"

    @property
    def detail_path(self) -> Path:
        return self.root / "record.md"


def record_experiment(
    meta: ExperimentMeta,
    status: str,
    steps: list[str],
    artifacts: list[str],
    conclusion: str,
) -> None:
    meta.root.mkdir(parents=True, exist_ok=True)
    detail = [
        f"# {meta.slug}",
        "",
        f"- 目标：{meta.goal}",
        f"- 状态：{status}",
        "",
        "## 过程记录",
        "",
    ]
    detail.extend(f"- {step}" for step in steps)
    detail.extend(["", "## 产物", ""])
    detail.extend(f"- {artifact}" for artifact in artifacts)
    detail.extend(["", "## 结论", "", f"- {conclusion}", ""])
    meta.detail_path.write_text("\n".join(detail), encoding="utf-8")

    summary = (
        f"## {meta.slug}\n\n"
        f"- 状态：{status}\n"
        f"- 结论：{conclusion}\n"
        f"- 详情：`{meta.slug}/record.md`\n"
    )
    _upsert_summary(meta.slug, summary)


def _upsert_summary(slug: str, section: str) -> None:
    marker_start = f"<!-- {slug}:start -->"
    marker_end = f"<!-- {slug}:end -->"
    block = f"{marker_start}\n{section}\n{marker_end}\n"
    if SUMMARY_PATH.exists():
        content = SUMMARY_PATH.read_text(encoding="utf-8")
    else:
        content = "# Lab Records\n\n用于汇总每个实验的高度概括结论。\n"
    pattern = re.compile(
        rf"{re.escape(marker_start)}.*?{re.escape(marker_end)}\n?",
        re.DOTALL,
    )
    if pattern.search(content):
        updated = pattern.sub(block, content)
    else:
        updated = content.rstrip() + "\n\n" + block
    SUMMARY_PATH.write_text(updated, encoding="utf-8")
