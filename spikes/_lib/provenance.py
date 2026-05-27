from __future__ import annotations

import hashlib
import json
import platform
import secrets
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _git(*args: str, cwd: Path | None = None) -> str:
    try:
        out = subprocess.check_output(
            ["git", *args],
            cwd=cwd,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def _short_sha(cwd: Path | None = None) -> str:
    sha = _git("rev-parse", "HEAD", cwd=cwd)
    return sha[:7] if sha else "nogit"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def new_run_id(cwd: Path | None = None) -> str:
    return f"{_utc_stamp()}-{_short_sha(cwd)}-{secrets.token_hex(3)}"


def hash_inputs(paths: list[Path]) -> str:
    h = hashlib.sha256()
    for p in sorted(paths):
        h.update(str(p).encode())
        if p.is_file():
            with p.open("rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
    return h.hexdigest()[:16]


@dataclass
class Manifest:
    run_id: str
    spike: str
    started_utc: str
    git_sha: str
    git_dirty: bool
    host: dict[str, str]
    inputs: dict[str, str] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)


def open_run(
    spike: str,
    results_root: Path,
    inputs: dict[str, Path] | None = None,
    config: dict[str, Any] | None = None,
    repo_root: Path | None = None,
) -> tuple[Path, Manifest]:
    repo_root = repo_root or Path.cwd()
    run_id = new_run_id(repo_root)
    run_dir = results_root / run_id
    (run_dir / "raw").mkdir(parents=True, exist_ok=True)

    sha = _git("rev-parse", "HEAD", cwd=repo_root)
    dirty = bool(_git("status", "--porcelain", cwd=repo_root))

    manifest = Manifest(
        run_id=run_id,
        spike=spike,
        started_utc=datetime.now(timezone.utc).isoformat(),
        git_sha=sha,
        git_dirty=dirty,
        host={
            "platform": platform.platform(),
            "python": platform.python_version(),
            "machine": platform.machine(),
        },
        inputs={k: hash_inputs([v]) for k, v in (inputs or {}).items()},
        config=dict(config or {}),
    )
    (run_dir / "manifest.json").write_text(json.dumps(asdict(manifest), indent=2))
    return run_dir, manifest


def write_result(run_dir: Path, framework: str, payload: dict[str, Any]) -> Path:
    fw_dir = run_dir / "raw" / framework
    fw_dir.mkdir(parents=True, exist_ok=True)
    out = fw_dir / "result.json"
    out.write_text(json.dumps(payload, indent=2, default=str))
    return out
