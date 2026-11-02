"""Deployment-only lifecycle management for the colocated Prometheus process.

When PROMETHEUS_BIN is unset (normal local Eclipse workflow), this module is a no-op
and the collector continues using the locally started Prometheus instance.
"""
import os
import subprocess
import time
from typing import Optional

import requests

_process: Optional[subprocess.Popen] = None


def start_prometheus() -> None:
    global _process
    binary = os.getenv("PROMETHEUS_BIN")
    config = os.getenv("PROMETHEUS_CONFIG")
    if not binary or not config:
        return

    if _process is not None and _process.poll() is None:
        return

    data_dir = os.getenv("PROMETHEUS_DATA_DIR", "/tmp/prometheus-data")
    os.makedirs(data_dir, exist_ok=True)
    _process = subprocess.Popen(
        [
            binary,
            f"--config.file={config}",
            f"--storage.tsdb.path={data_dir}",
            "--web.listen-address=127.0.0.1:9090",
            "--web.enable-lifecycle",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )

    ready_url = os.getenv("PROMETHEUS_URL", "http://127.0.0.1:9090").rstrip("/") + "/-/ready"
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if _process.poll() is not None:
            _process = None
            raise RuntimeError("Prometheus exited before becoming ready. Check its deployment configuration.")
        try:
            response = requests.get(ready_url, timeout=1)
            if response.ok:
                return
        except requests.RequestException:
            pass
        time.sleep(0.5)

    stop_prometheus()
    raise RuntimeError("Prometheus did not become ready within 30 seconds.")


def stop_prometheus() -> None:
    global _process
    if _process is None:
        return
    if _process.poll() is None:
        _process.terminate()
        try:
            _process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _process.kill()
            _process.wait(timeout=3)
    _process = None
