"""Configuration: config.yaml + environment overrides for secrets."""
from __future__ import annotations

import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "config.yaml"


def load_config(path: str | os.PathLike | None = None) -> dict:
    p = Path(path or os.environ.get("GARAGE_CONFIG", DEFAULT_CONFIG))
    with open(p, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    # data directory
    cfg.setdefault("data_dir", str(ROOT / "data"))
    cfg["data_dir"] = os.environ.get("GARAGE_DATA_DIR", cfg["data_dir"])
    Path(cfg["data_dir"]).mkdir(parents=True, exist_ok=True)

    # secrets never live in YAML: read from environment (.env is loaded by the CLI)
    email = cfg.setdefault("email", {})
    email["smtp_host"] = os.environ.get("SMTP_HOST", email.get("smtp_host", "smtp.mail.me.com"))
    email["smtp_port"] = int(os.environ.get("SMTP_PORT", email.get("smtp_port", 587)))
    email["smtp_user"] = os.environ.get("SMTP_USER", email.get("smtp_user", ""))
    email["smtp_password"] = os.environ.get("SMTP_PASSWORD", email.get("smtp_password", ""))
    email["sender"] = os.environ.get("SMTP_SENDER", email.get("sender") or email["smtp_user"])
    email["recipient"] = os.environ.get("REPORT_RECIPIENT", email.get("recipient", "alexmrt@icloud.com"))
    email["dry_run"] = os.environ.get("EMAIL_DRY_RUN", str(email.get("dry_run", False))).lower() in ("1", "true", "yes")
    return cfg


def load_dotenv(path: str | os.PathLike | None = None) -> None:
    """Minimal .env loader (KEY=VALUE lines) so we don't depend on python-dotenv."""
    p = Path(path or ROOT / ".env")
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
