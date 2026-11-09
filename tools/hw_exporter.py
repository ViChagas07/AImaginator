"""Exporter Prometheus opcional para Windows (manual; nao roda em CI).

Le RAM via psutil, contadores 'GPU Adapter Memory' do Windows e, se
HW_SENSOR_URL estiver definido, o JSON do LibreHardwareMonitor.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.request

import psutil
from prometheus_client import Gauge, start_http_server

GPU_MEMORY = Gauge("aimaginator_gpu_dedicated_bytes", "GPU dedicated memory")
FREE_RAM = Gauge("aimaginator_host_free_ram_bytes", "Host free RAM")
HOTTEST = Gauge("aimaginator_host_max_temp_celsius", "Max temperature")


def _gpu_memory_bytes() -> float:
    try:
        result = subprocess.run(  # noqa: S603
            [  # noqa: S607
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-Counter '\\GPU Adapter Memory(*)\\Dedicated Usage')."
                "CounterSamples | Measure-Object CookedValue -Sum | "
                "Select-Object -ExpandProperty Sum",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return float(result.stdout.strip().replace(",", "."))
    except (ValueError, OSError, subprocess.SubprocessError):
        return 0.0


def _lhm_temp(url: str) -> float | None:
    if not url:
        return None
    try:
        with urllib.request.urlopen(url, timeout=3) as response:  # noqa: S310
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None
    values: list[float] = []

    def walk(node) -> None:
        if isinstance(node, dict):
            text = str(node.get("Text") or "").lower()
            value = node.get("Value")
            if "temp" in text and isinstance(value, int | float):
                values.append(float(value))
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(payload)
    return max(values) if values else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=9200)
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("--lhm-url", default="")
    args = parser.parse_args()
    start_http_server(args.port)
    print(f"hw_exporter em :{args.port} (Ctrl+C para parar)")
    while True:
        FREE_RAM.set(psutil.virtual_memory().available)
        GPU_MEMORY.set(_gpu_memory_bytes())
        temp = _lhm_temp(args.lhm_url)
        if temp is not None:
            HOTTEST.set(temp)
        time.sleep(max(1.0, args.interval))


if __name__ == "__main__":
    raise SystemExit(main())
