"""Local settings shared by every chapter, read from project/.env (see .env.template)."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def project_root(start: Path | None = None) -> Path:
    """Walk up from `start` (default: cwd) to the folder holding pyproject.toml."""
    here = (start or Path.cwd()).resolve()
    for d in [here, *here.parents, here / "project"]:
        if (d / "pyproject.toml").exists() and (d / "src" / "openmetadata_tutorial").exists():
            return d
    return Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    om_url: str            # http://localhost:18585 (UI and API, API under /api)
    om_admin_email: str
    om_admin_password: str
    om_jwt_token: str      # ingestion-bot token written by `just token`; "" until then
    shop_host: str         # shopdb as seen from the host
    shop_port: int
    shop_db: str
    shop_admin_user: str
    shop_admin_password: str
    shop_reader_user: str  # the read-only user OpenMetadata ingestion connects with
    shop_reader_password: str
    webhook_url: str       # http://localhost:18090 (alert receiver, chapter 09)

    @property
    def om_api(self) -> str:
        return f"{self.om_url}/api"


def settings(root: Path | None = None) -> Settings:
    root = root or project_root()
    load_dotenv(root / ".env", override=True)
    e = os.environ.get
    return Settings(
        om_url=e("OM_URL", "http://localhost:18585"),
        om_admin_email=e("OM_ADMIN_EMAIL", "admin@open-metadata.org"),
        om_admin_password=e("OM_ADMIN_PASSWORD", "admin"),
        om_jwt_token=e("OM_JWT_TOKEN", ""),
        shop_host=e("SHOP_HOST", "localhost"),
        shop_port=int(e("SHOP_PORT", "15433")),
        shop_db=e("SHOP_DB", "brightcup"),
        shop_admin_user=e("SHOP_ADMIN_USER", "shop_admin"),
        shop_admin_password=e("SHOP_ADMIN_PASSWORD", "shop123"),
        shop_reader_user=e("SHOP_READER_USER", "om_reader"),
        shop_reader_password=e("SHOP_READER_PASSWORD", "reader123"),
        webhook_url=e("WEBHOOK_URL", "http://localhost:18090"),
    )
