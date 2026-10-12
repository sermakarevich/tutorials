"""Chapter 04: scheduled ingestion pipelines for the sandbox service.

The CLI runs (`just ingest ch04_sandbox`) send metadata straight to the REST
API and leave no pipeline record in OpenMetadata. A *scheduled* run is the
opposite: an ingestion-pipeline entity stored in OpenMetadata, deployed as a
DAG to Airflow, with a status history per run.

Run from project/ as, e.g.::

    uv run python -m openmetadata_tutorial.ch04_pipelines ensure
    uv run python -m openmetadata_tutorial.ch04_pipelines status
"""

import sys
import time

from openmetadata_tutorial import client

#: The playground this chapter owns. Never service brightcup_pg.
SERVICE = "brightcup_sandbox"

#: The scheduled pipeline. Fixed name, so re-running is create-or-update.
PIPELINE_NAME = "ch04_sandbox_metadata"

#: Daily at 02:00 UTC, cron format (Airflow scheduleInterval).
SCHEDULE = "0 2 * * *"


def service_ref(name: str = SERVICE) -> dict:
    """The EntityReference a pipeline create call needs for `service`."""
    svc = client.get(f"/v1/services/databaseServices/name/{name}")
    return {"id": svc["id"], "type": "databaseService"}


def ensure_pipeline(name: str = PIPELINE_NAME) -> dict:
    """Create (or reuse) the daily metadata pipeline for the sandbox service.

    Returns {"fqn", "id", "how"} where how is "created" or "already there".
    """
    existing = client.get("/v1/services/ingestionPipelines", service=SERVICE, limit=50)
    for p in existing.get("data", []):
        if p["name"] == name:
            return {"fqn": p["fullyQualifiedName"], "id": p["id"], "how": "already there"}
    body = {
        "name": name,
        "displayName": "ch04 sandbox metadata (daily)",
        "description": "Daily metadata ingestion of the sandbox schema (chapter 04 playground).",
        "pipelineType": "metadata",
        "service": service_ref(),
        "sourceConfig": {
            "config": {
                "type": "DatabaseMetadata",
                "includeTables": True,
                "includeViews": True,
                "markDeletedTables": True,
                "schemaFilterPattern": {"includes": ["^sandbox$"]},
            }
        },
        "airflowConfig": {"scheduleInterval": SCHEDULE},
    }
    r = client.api("POST", "/v1/services/ingestionPipelines", json=body).json()
    return {"fqn": r["fullyQualifiedName"], "id": r["id"], "how": "created"}


def deploy(pipeline_id: str) -> dict:
    """Deploy the pipeline as a DAG to Airflow; return the platform reply."""
    return client.api("POST", f"/v1/services/ingestionPipelines/deploy/{pipeline_id}").json()


def trigger(pipeline_id: str) -> dict:
    """Trigger one run now; return the platform reply."""
    return client.api("POST", f"/v1/services/ingestionPipelines/trigger/{pipeline_id}").json()


def statuses(days: int = 30, name: str = PIPELINE_NAME) -> dict:
    """Status history of the pipeline (FQN addressing; by id 404s in 2.0.5).

    Returns {"fqn", "runs": [...]} with one entry per recorded run.
    """
    info = ensure_pipeline(name)
    now = int(time.time() * 1000)
    r = client.get(
        f"/v1/services/ingestionPipelines/{info['fqn']}/pipelineStatus",
        startTs=now - days * 86400 * 1000,
        endTs=now,
    )
    runs = [
        {"runId": s.get("runId"), "state": s.get("pipelineState"), "startDate": s.get("startDate")}
        for s in r.get("data", [])
    ]
    return {"fqn": info["fqn"], "runs": runs, "how": info["how"]}


def pipeline_count(service: str = SERVICE) -> int:
    """How many ingestion pipelines reference `service` (0 for CLI-only runs)."""
    return client.get("/v1/services/ingestionPipelines", service=service, limit=50)["paging"]["total"]


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "ensure"
    if action == "ensure":
        info = ensure_pipeline()
        print(info)
        print(deploy(info["id"]))
    elif action == "trigger":
        print(trigger(ensure_pipeline()["id"]))
    elif action == "status":
        print(statuses())
    elif action == "count":
        print({"service": SERVICE, "pipelines": pipeline_count(SERVICE)})
    else:
        raise SystemExit(f"unknown action {action!r}; use ensure|trigger|status|count")
