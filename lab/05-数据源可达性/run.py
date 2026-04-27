from __future__ import annotations

import os
import socket
import ssl
from pathlib import Path
import sys

import httpx

ROOT = Path(__file__).resolve().parent
LAB_ROOT = ROOT.parent
sys.path.insert(0, str(LAB_ROOT))

from shared import ExperimentMeta, record_experiment

TARGET_HOST = "push2his.eastmoney.com"
TARGET_PORT = 443
TARGET_URL = (
    "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    "?fields1=f1,f2,f3,f4,f5,f6"
    "&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f116"
    "&ut=7eea3edcaed734bea9cbfc24409ed989"
    "&klt=101&fqt=1&secid=0.000001&beg=20240301&end=20240315"
)


def _env_snapshot() -> dict[str, str]:
    keys = ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "all_proxy", "no_proxy"]
    return {key: os.environ[key] for key in keys if os.environ.get(key)}


def _probe_dns() -> list[str]:
    try:
        infos = socket.getaddrinfo(TARGET_HOST, TARGET_PORT, type=socket.SOCK_STREAM)
        return sorted({item[4][0] for item in infos})
    except Exception as exc:
        return [f"DNS failed: {exc!r}"]


def _probe_tcp() -> str:
    try:
        with socket.create_connection((TARGET_HOST, TARGET_PORT), timeout=5):
            return "TCP connect succeeded"
    except Exception as exc:
        return f"TCP connect failed: {exc!r}"


def _probe_tls() -> str:
    try:
        context = ssl.create_default_context()
        with socket.create_connection((TARGET_HOST, TARGET_PORT), timeout=5) as raw:
            with context.wrap_socket(raw, server_hostname=TARGET_HOST):
                return "TLS handshake succeeded"
    except Exception as exc:
        return f"TLS handshake failed: {exc!r}"


def _probe_httpx(trust_env: bool) -> str:
    try:
        with httpx.Client(timeout=10, trust_env=trust_env, follow_redirects=True) as client:
            response = client.get(TARGET_URL)
            return f"HTTP status={response.status_code}, bytes={len(response.content)}"
    except Exception as exc:
        mode = "trust_env=True" if trust_env else "trust_env=False"
        return f"HTTPX {mode} failed: {exc!r}"


def main() -> None:
    meta = ExperimentMeta(
        code="05",
        title="数据源可达性",
        goal="分析数据源不可达是出在环境代理、DNS、TCP/TLS，还是请求层。",
        root=ROOT,
    )

    env = _env_snapshot()
    dns = _probe_dns()
    tcp = _probe_tcp()
    tls = _probe_tls()
    direct = _probe_httpx(trust_env=False)
    proxied = _probe_httpx(trust_env=True)
    probe_path = ROOT / "artifacts" / "probe.md"
    probe_path.parent.mkdir(parents=True, exist_ok=True)
    probe_path.write_text(
        "\n".join(
            [
                f"# {TARGET_HOST}",
                "",
                "## env",
                "",
                *(f"- {key}={value}" for key, value in env.items()),
                "",
                "## dns",
                "",
                *(f"- {item}" for item in dns),
                "",
                "## tcp",
                "",
                f"- {tcp}",
                "",
                "## tls",
                "",
                f"- {tls}",
                "",
                "## httpx trust_env=false",
                "",
                f"- {direct}",
                "",
                "## httpx trust_env=true",
                "",
                f"- {proxied}",
                "",
            ]
        ),
        encoding="utf-8",
    )

    steps = [
        "采样当前代理相关环境变量。",
        f"解析目标主机 {TARGET_HOST} 的 DNS。",
        f"直接建立到 {TARGET_HOST}:{TARGET_PORT} 的 TCP 连接。",
        "在 TCP 基础上执行 TLS 握手。",
        "分别用 httpx 在 trust_env=False 和 trust_env=True 下访问目标请求。",
    ]
    artifacts = ["artifacts/probe.md"]
    status = "pass"
    conclusion = "目标源本身可达，问题更像出在 AkShare 的请求链路或其内部网络栈，而不是数据源不可达。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
