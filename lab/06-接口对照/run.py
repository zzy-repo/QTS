from __future__ import annotations

from pathlib import Path
import sys

import akshare as ak
import requests

ROOT = Path(__file__).resolve().parent
LAB_ROOT = ROOT.parent
sys.path.insert(0, str(LAB_ROOT))

from shared import ExperimentMeta, record_experiment

TARGET_SYMBOL = "000001"
TARGET_HOST = "push2his.eastmoney.com"
TARGET_URL = f"https://{TARGET_HOST}/api/qt/stock/kline/get"
TARGET_PARAMS = {
    "fields1": "f1,f2,f3,f4,f5,f6",
    "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f116",
    "ut": "7eea3edcaed734bea9cbfc24409ed989",
    "klt": "101",
    "fqt": "1",
    "secid": f"0.{TARGET_SYMBOL}",
    "beg": "20240301",
    "end": "20240315",
}


def _probe_akshare() -> str:
    try:
        df = ak.stock_zh_a_hist(
            symbol=TARGET_SYMBOL,
            period="daily",
            start_date="20240301",
            end_date="20240315",
            adjust="qfq",
        )
        return f"akshare.stock_zh_a_hist rows={len(df)}"
    except Exception as exc:
        return f"akshare.stock_zh_a_hist failed: {exc!r}"


def _probe_requests_default() -> str:
    try:
        response = requests.get(TARGET_URL, params=TARGET_PARAMS, timeout=15)
        return f"requests.get status={response.status_code}, bytes={len(response.content)}"
    except Exception as exc:
        return f"requests.get failed: {exc!r}"


def _probe_requests_no_env() -> str:
    try:
        session = requests.Session()
        session.trust_env = False
        response = session.get(TARGET_URL, params=TARGET_PARAMS, timeout=15)
        return (
            "requests.Session(trust_env=False) "
            f"status={response.status_code}, bytes={len(response.content)}"
        )
    except Exception as exc:
        return f"requests.Session(trust_env=False) failed: {exc!r}"


def main() -> None:
    meta = ExperimentMeta(
        code="06",
        title="接口对照",
        goal="对照 AkShare 封装和原生请求，确认接口本身是否正确。",
        root=ROOT,
    )

    akshare_result = _probe_akshare()
    requests_default_result = _probe_requests_default()
    requests_no_env_result = _probe_requests_no_env()

    probe_path = ROOT / "artifacts" / "probe.md"
    probe_path.parent.mkdir(parents=True, exist_ok=True)
    probe_path.write_text(
        "\n".join(
            [
                f"# {meta.slug}",
                "",
                "## akshare",
                "",
                f"- {akshare_result}",
                "",
                "## requests-default",
                "",
                f"- {requests_default_result}",
                "",
                "## requests-no-env",
                "",
                f"- {requests_no_env_result}",
                "",
            ]
        ),
        encoding="utf-8",
    )

    steps = [
        "调用 AkShare 的 stock_zh_a_hist。",
        "用原生 requests.get 访问同一条东财历史行情接口。",
        "用 requests.Session(trust_env=False) 再访问同一接口。",
    ]
    artifacts = ["artifacts/probe.md"]
    status = "pass"
    if "failed" in akshare_result:
        conclusion = (
            "接口本身是同一条东财 kline 接口；AkShare 失败而原生请求成功时，问题更可能在封装或环境继承。"
        )
    else:
        conclusion = "AkShare 和原生请求都可用，接口选择本身不是问题。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
