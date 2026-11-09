"""Gate de auditoria: falha em vulnerabilidades nao exceptuadas.

Uso:
    python tools/security/audit_gate.py pip pip-audit.json .github/security-exceptions.json
    python tools/security/audit_gate.py npm npm-audit.json .github/security-exceptions.json
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _allowed(exceptions: dict, ecosystem: str, vuln_id: str) -> bool:
    today = date.today().isoformat()
    for item in exceptions.get(ecosystem, []):
        if item.get("id") == vuln_id and item.get("expires", "1970-01-01") >= today:
            return True
    return False


def _pip(report: dict, exceptions: dict) -> list[str]:
    failures: list[str] = []
    for dep in report.get("dependencies", []):
        for vuln in dep.get("vulns") or []:
            vuln_id = vuln.get("id", "unknown")
            if not _allowed(exceptions, "pip", vuln_id):
                failures.append(f"{dep.get('name')} {vuln_id}")
    return failures


def _npm(report: dict, exceptions: dict) -> list[str]:
    failures: list[str] = []
    for name, vuln in (report.get("vulnerabilities") or {}).items():
        severity = vuln.get("severity")
        if severity not in {"high", "critical"}:
            continue
        ids = []
        for via in vuln.get("via") or []:
            if isinstance(via, dict) and via.get("source"):
                ids.append(str(via["source"]))
        if not ids:
            ids = [name]
        if not any(_allowed(exceptions, "npm", item) for item in ids):
            failures.append(f"{name} ({severity})")
    return failures


def main() -> int:
    if len(sys.argv) != 4:
        print("uso: audit_gate.py pip|npm report.json exceptions.json")
        return 2
    ecosystem, report_path, exceptions_path = sys.argv[1:]
    report = _load(report_path)
    exceptions = _load(exceptions_path)
    failures = _pip(report, exceptions) if ecosystem == "pip" else _npm(
        report, exceptions
    )
    if failures:
        print("FALHA auditoria:")
        for item in failures:
            print(f"- {item}")
        return 1
    print("auditoria ok (sem High/Critical nao exceptuados)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
