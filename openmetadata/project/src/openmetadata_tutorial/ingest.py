"""Run an ingestion workflow YAML from project/ingestion/ with the `metadata` CLI.

The workflow runs INSIDE the om-tutorial-ingestion container, so it sees the same
network as the server: the shop database is `shopdb:5432` and the server is
`http://openmetadata-server:8585/api` -- the same addresses the stored service
connection and UI-scheduled runs use. The YAML holds ${OM_JWT_TOKEN},
${SHOP_READER_PASSWORD}, ... placeholders; they are filled from .env here and the
result is piped into the container (secrets never land in a file in the repo).

`python -m openmetadata_tutorial.ingest ingest ingestion/metadata.yaml`
"""

import os
import subprocess
import sys

from openmetadata_tutorial.config import project_root, settings

CONTAINER = "om-tutorial-ingestion"
COMMANDS = {"ingest", "usage", "profile", "test", "classify"}


def render(yaml_file: str) -> str:
    """Return the YAML text with ${VAR} placeholders filled from .env / the environment."""
    settings()  # loads .env into os.environ
    text = (project_root() / yaml_file).read_text()
    if "${OM_JWT_TOKEN}" in text and not os.environ.get("OM_JWT_TOKEN"):
        raise SystemExit("OM_JWT_TOKEN not set: run `just token` first")
    return os.path.expandvars(text)


def run(command: str, yaml_file: str) -> int:
    """`metadata <command> -c <rendered yaml>` inside the ingestion container; return its exit code."""
    if command not in COMMANDS:
        raise SystemExit(f"command must be one of {sorted(COMMANDS)}")
    name = os.path.basename(yaml_file)
    script = f"cat > /tmp/{name} && metadata {command} -c /tmp/{name}; rc=$?; rm -f /tmp/{name}; exit $rc"
    return subprocess.run(
        ["docker", "exec", "-i", CONTAINER, "bash", "-c", script], input=render(yaml_file), text=True
    ).returncode


if __name__ == "__main__":
    sys.exit(run(sys.argv[1], sys.argv[2]))
