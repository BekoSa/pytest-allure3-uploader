from __future__ import annotations

import io
import json
import os
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Union

import requests


@dataclass
class UploadResult:
    project: str
    run_id: int
    ui_url: str
    latest_url: str
    status: str
    error: Optional[str] = None


class AllureUploaderClient:
    def __init__(
        self,
        base_url: str,
        timeout_s: float = 60.0,
        verify_tls: bool = True,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.verify_tls = verify_tls
        self.session = requests.Session()
        if headers:
            self.session.headers.update(headers)

    @staticmethod
    def zip_allure_results(results_dir: Union[str, Path]) -> bytes:
        p = Path(results_dir)
        if not p.exists() or not p.is_dir():
            raise FileNotFoundError(f"allure results dir not found: {p}")

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for file_path in p.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(p).as_posix()
                    zf.write(file_path, arcname=arcname)

        return buf.getvalue()

    def upload(
        self,
        project: str,
        results_dir: Union[str, Path],
        meta: Optional[Dict[str, Any]] = None,
        config: Optional[Union[str, Path]] = None,
    ) -> UploadResult:
        """
        Uploads allure-results to allure3-docker-service.

        Multipart fields:
          - results: zip bytes
          - meta: json string (application/json)
          - config: optional (text js OR file js)
        """
        meta = meta or {}
        url = f"{self.base_url}/api/v1/projects/{project}/runs"

        zip_bytes = self.zip_allure_results(results_dir)

        files: Dict[str, Any] = {
            "results": ("allure-results.zip", zip_bytes, "application/zip"),
            "meta": (None, json.dumps(meta), "application/json"),
        }

        # NEW: optional config
        if config is not None:
            if isinstance(config, (str,)):
                cfg_text = config.strip()
                if cfg_text:
                    files["config"] = ("allure.config.mjs", cfg_text, "text/javascript")
            else:
                cfg_path = Path(config)
                if not cfg_path.exists() or not cfg_path.is_file():
                    raise FileNotFoundError(f"config file not found: {cfg_path}")
                # requests закроет файл после запроса не всегда гарантированно — лучше через bytes
                cfg_bytes = cfg_path.read_bytes()
                files["config"] = (cfg_path.name, cfg_bytes, "text/javascript")

        resp = self.session.post(
            url,
            files=files,
            timeout=self.timeout_s,
            verify=self.verify_tls,
        )

        content_type = resp.headers.get("content-type", "")
        if "application/json" not in content_type:
            # если сервер вернул html/text — покажем как есть
            resp.raise_for_status()
            raise RuntimeError(f"Unexpected response content-type: {content_type}")

        data = resp.json()
        return UploadResult(
            project=data.get("project", project),
            run_id=int(data.get("run_id", 0)),
            ui_url=data.get("ui_url", ""),
            latest_url=data.get("latest_url", ""),
            status=data.get("status", "unknown"),
            error=data.get("error"),
        )


def default_meta_from_env() -> Dict[str, Any]:
    return {
        "trigger": os.getenv("CI_PIPELINE_SOURCE") or os.getenv("GITHUB_EVENT_NAME") or "local",
        "branch": os.getenv("CI_COMMIT_REF_NAME") or os.getenv("GITHUB_REF_NAME"),
        "commit": os.getenv("CI_COMMIT_SHA") or os.getenv("GITHUB_SHA"),
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
