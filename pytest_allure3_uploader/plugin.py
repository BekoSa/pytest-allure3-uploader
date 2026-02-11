from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

import pytest

from .client import AllureUploaderClient, default_meta_from_env


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("allure-uploader")

    group.addoption("--allure-upload", action="store_true", default=False)
    group.addoption("--allure-upload-url", action="store", default=os.getenv("ALLURE_UPLOAD_URL", ""))
    group.addoption("--allure-upload-project", action="store", default=os.getenv("ALLURE_UPLOAD_PROJECT", ""))
    group.addoption("--allure-results-dir", action="store", default=os.getenv("ALLURE_RESULTS_DIR", "allure-results"))
    group.addoption("--allure-upload-timeout", action="store", default=os.getenv("ALLURE_UPLOAD_TIMEOUT", "60"))
    group.addoption("--allure-upload-insecure", action="store_true", default=False)


def _get_alluredir_if_any(config: pytest.Config) -> Optional[str]:
    for key in ("alluredir", "--alluredir"):
        try:
            v = config.getoption(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
        except Exception:
            continue
    return None


def _get_results_dir(config: pytest.Config) -> str:
    explicit = (config.getoption("--allure-results-dir") or "").strip()
    if explicit and explicit != "allure-results":
        return explicit

    alluredir = _get_alluredir_if_any(config)
    if alluredir:
        return alluredir

    return explicit or "allure-results"


def _collect_pytest_stats(config: pytest.Config) -> Dict[str, int]:
    tr = config.pluginmanager.get_plugin("terminalreporter")
    out: Dict[str, int] = {}

    if not tr:
        return out

    stats = getattr(tr, "stats", None)
    if not isinstance(stats, dict):
        return out

    for k in ("passed", "failed", "skipped", "error", "xfailed", "xpassed"):
        v = stats.get(k)
        if isinstance(v, list):
            out[k] = len(v)

    return out


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    config = session.config

    if not config.getoption("--allure-upload"):
        return

    base_url = (config.getoption("--allure-upload-url") or "").strip()
    project = (config.getoption("--allure-upload-project") or "").strip()
    timeout = float(config.getoption("--allure-upload-timeout") or 60)
    verify_tls = not bool(config.getoption("--allure-upload-insecure"))

    results_dir_str = _get_results_dir(config)
    results_dir = Path(results_dir_str)

    tr = config.pluginmanager.get_plugin("terminalreporter")

    if not base_url or not project:
        if tr:
            tr.write_line("[allure-uploader] Missing URL or project")
        return

    if not results_dir.exists():
        if tr:
            tr.write_line(f"[allure-uploader] Results dir not found: {results_dir}")
        return

    meta: Dict[str, Any] = default_meta_from_env()
    meta["pytest_exitstatus"] = exitstatus
    meta["pytest_stats"] = _collect_pytest_stats(config)

    try:
        client = AllureUploaderClient(
            base_url=base_url,
            timeout_s=timeout,
            verify_tls=verify_tls,
        )

        res = client.upload(project=project, results_dir=results_dir, meta=meta)

        if tr:
            tr.write_sep("=", "Allure upload")
            tr.write_line(f"project: {res.project}")
            tr.write_line(f"run_id: {res.run_id}")
            tr.write_line(f"status: {res.status}")
            tr.write_line(f"ui: {base_url}{res.ui_url}")
            tr.write_line(f"latest: {base_url}{res.latest_url}")

    except Exception as e:
        if tr:
            tr.write_sep("=", "Allure upload FAILED")
            tr.write_line(str(e))
