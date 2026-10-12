"""Fetch the ingestion-bot JWT and store it in project/.env as OM_JWT_TOKEN (`just token`)."""

from openmetadata_tutorial.client import bot_token
from openmetadata_tutorial.config import project_root


def write_token() -> str:
    env = project_root() / ".env"
    tok = bot_token()
    lines = [l for l in env.read_text().splitlines() if not l.startswith("OM_JWT_TOKEN=")] if env.exists() else []
    env.write_text("\n".join([*lines, f"OM_JWT_TOKEN={tok}"]) + "\n")
    return tok


if __name__ == "__main__":
    tok = write_token()
    print(f"OM_JWT_TOKEN written to .env ({len(tok)} chars, starts {tok[:12]}...)")
