"""Talking to the OpenMetadata server: login, bot token, raw REST calls, the Python SDK client.

Every chapter that calls the API goes through these helpers, so auth is done one way.
"""

import base64

import requests

from openmetadata_tutorial.config import Settings, settings

TIMEOUT = 30


def login_token(s: Settings | None = None) -> str:
    """Log in as the admin user (basic auth) and return a short-lived user JWT."""
    s = s or settings()
    pw = base64.b64encode(s.om_admin_password.encode()).decode()
    r = requests.post(f"{s.om_api}/v1/users/login", json={"email": s.om_admin_email, "password": pw}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()["accessToken"]


def bot_token(bot: str = "ingestion-bot", s: Settings | None = None) -> str:
    """Return the long-lived JWT of a bot (default: ingestion-bot), read with the admin's login."""
    s = s or settings()
    h = {"Authorization": f"Bearer {login_token(s)}"}
    r = requests.get(f"{s.om_api}/v1/bots/name/{bot}", headers=h, timeout=TIMEOUT)
    r.raise_for_status()
    bot_user_id = r.json()["botUser"]["id"]
    r = requests.get(f"{s.om_api}/v1/users/auth-mechanism/{bot_user_id}", headers=h, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()["config"]["JWTToken"]


def token(s: Settings | None = None) -> str:
    """The token chapters use: OM_JWT_TOKEN from .env, else a fresh admin login."""
    s = s or settings()
    return s.om_jwt_token or login_token(s)


def api(method: str, path: str, s: Settings | None = None, **kwargs) -> requests.Response:
    """Call the REST API, e.g. api("GET", "/v1/tables/name/brightcup_pg.brightcup.raw.orders").

    `path` starts after /api. Raises on HTTP errors; returns the Response.
    """
    s = s or settings()
    headers = {"Authorization": f"Bearer {token(s)}", **kwargs.pop("headers", {})}
    if method.upper() == "PATCH":
        headers.setdefault("Content-Type", "application/json-patch+json")
    r = requests.request(method, f"{s.om_api}{path}", headers=headers, timeout=TIMEOUT, **kwargs)
    r.raise_for_status()
    return r


def get(path: str, **params) -> dict:
    """GET a path and return its JSON, e.g. get("/v1/tables", limit=5, fields="owners")."""
    return api("GET", path, params=params).json()


def sdk():
    """The official Python SDK client (metadata.ingestion.ometa.ometa_api.OpenMetadata)."""
    from metadata.generated.schema.entity.services.connections.metadata.openMetadataConnection import (
        OpenMetadataConnection,
    )
    from metadata.generated.schema.security.client.openMetadataJWTClientConfig import OpenMetadataJWTClientConfig
    from metadata.ingestion.ometa.ometa_api import OpenMetadata

    s = settings()
    conn = OpenMetadataConnection(
        hostPort=s.om_api,
        authProvider="openmetadata",
        securityConfig=OpenMetadataJWTClientConfig(jwtToken=token(s)),
    )
    return OpenMetadata(conn)
