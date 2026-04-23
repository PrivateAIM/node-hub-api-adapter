"""EPs for retrieving logged events."""

import datetime
import json
import logging
import re
import uuid
from typing import Annotated

import httpx
from fastapi import APIRouter, HTTPException, Query, Security, Path
from starlette import status

from hub_adapter.auth import verify_idp_token, jwtbearer
from hub_adapter.constants import ServiceTag
from hub_adapter.dependencies import get_settings, make_log_hook
from hub_adapter.schemas.logs import AnalysisLogHistoryResponse, AnalysisLogsResponse, EventLogResponse

logger = logging.getLogger(__name__)

logs_router = APIRouter(
    dependencies=[
        Security(verify_idp_token),
        Security(jwtbearer),
    ],
    tags=[ServiceTag.LOGS],
    responses={404: {"description": "Not found"}},
)


def count_logs(query: str, params: dict | None = None) -> int:
    """Return the total number of logs matching a query, ignoring limit/offset."""
    settings = get_settings()
    count_params = {k: v for k, v in (params or {}).items() if k not in ("limit", "offset")}
    query_data = {"query": f"{query} | count() as total", **count_params}

    with httpx.Client(event_hooks={"response": [make_log_hook(ServiceTag.LOGS)]}) as client:
        resp = client.post(
            f"{settings.victoria_logs_url}/select/logsql/query",
            data=query_data,
        )
        resp.raise_for_status()

    for line in resp.text.strip().splitlines():
        if line:
            return int(json.loads(line).get("total", 0))

    return 0


def query_logs(query: str, params: dict | None = None):
    """Retrieve a selection of logs."""
    _fields = (
        "_msg",
        "kubernetes.container_image",
        "kubernetes.pod_labels.component",
        "level",
        "log.service",
        "log.timestamp",
        "log.user",
        "log.event_name",
    )
    _rename = {
        "_msg": "message",
        "kubernetes.container_image": "image",
        "kubernetes.pod_labels.component": "component",
        "log.service": "service",
        "log.timestamp": "timestamp",
        "log.user": "user",
        "log.event_name": "event_name",
    }
    settings = get_settings()

    rename_clause = ", ".join(f"{src} as {dst}" for src, dst in _rename.items())
    logsql_query = f"{query} | fields {', '.join(_fields)} | rename {rename_clause}"
    query_data = {"query": logsql_query, **params}

    _output_fields = {_rename.get(f, f) for f in _fields}

    with httpx.Client(event_hooks={"response": [make_log_hook(ServiceTag.LOGS)]}) as client:
        resp = client.post(
            f"{settings.victoria_logs_url}/select/logsql/query",
            data=query_data,
        )
        resp.raise_for_status()

    logs = []
    for line in resp.text.strip().splitlines():
        if line:
            entry = json.loads(line)
            logs.append({k: v for k, v in entry.items() if k in _output_fields})

    return logs


def _get_analysis_container_names(analysis_id_str: str) -> list[str]:
    """Return all unique container names matching the analysis ID pattern."""
    settings = get_settings()
    pattern = f"^(nginx-analysis|analysis)-{analysis_id_str}-[0-9]+$"
    query = f'kubernetes.container_name:~"{pattern}"'
    query_data = {
        "query": f"{query} | uniq by (kubernetes.container_name)",
        "limit": 100,
    }
    with httpx.Client(event_hooks={"response": [make_log_hook(ServiceTag.LOGS)]}) as client:
        resp = client.post(
            f"{settings.victoria_logs_url}/select/logsql/query",
            data=query_data,
        )
        resp.raise_for_status()

    names = []
    for line in resp.text.strip().splitlines():
        if line:
            name = json.loads(line).get("kubernetes.container_name", "")
            if name:
                names.append(name)
    return names


def _query_pod_logs(container_name: str) -> list[dict]:
    """Return log lines for a specific container, sorted oldest-first."""
    settings = get_settings()
    query = f'kubernetes.container_name:"{container_name}"'
    query_data = {
        "query": (f"{query} | fields _time, _msg | sort by (_time)"),
        "limit": 1000,
    }
    with httpx.Client(event_hooks={"response": [make_log_hook(ServiceTag.LOGS)]}) as client:
        resp = client.post(
            f"{settings.victoria_logs_url}/select/logsql/query",
            data=query_data,
        )
        resp.raise_for_status()

    logs = []
    for line in resp.text.strip().splitlines():
        if line:
            entry = json.loads(line)
            logs.append(
                {
                    "timestamp": entry.get("_time", ""),
                    "message": entry.get("_msg", ""),
                    # "pod_name": entry.get("kubernetes.pod_name"),
                    # "container_name": entry.get("kubernetes.container_name"),
                }
            )
    return logs


def _group_by_run(container_names: list[str]) -> dict[int, dict[str, str]]:
    """Group container names by integer run number extracted from the suffix."""
    runs: dict[int, dict[str, str]] = {}
    for name in container_names:
        match = re.search(r"-(\d+)$", name)
        if not match:
            continue
        run_num = int(match.group(1))
        runs.setdefault(run_num, {})
        if name.startswith("nginx-analysis-"):
            runs[run_num]["nginx"] = name
        elif name.startswith("analysis-"):
            runs[run_num]["analysis"] = name
    return runs


@logs_router.get(
    "/events",
    status_code=status.HTTP_200_OK,
    response_model=EventLogResponse,
    name="logs.events.get",
)
async def get_events(
    limit: Annotated[int | None, Query(description="Maximum number of events to return")] = 50,
    offset: Annotated[int | None, Query(description="Number of events to offset by")] = None,
    service_tag: Annotated[ServiceTag | None, Query(description="Filter events by service tag")] = None,
    username: Annotated[str | None, Query(description="Filter events by username")] = None,
    start_date: Annotated[
        datetime.datetime | None,
        Query(description="Filter events by start date using ISO8601 format"),
    ] = None,
    end_date: Annotated[
        datetime.datetime | None,
        Query(description="Filter events by end date using ISO8601 format"),
    ] = None,
):
    """Retrieve a selection of logged events."""
    settings = get_settings()
    if not settings.victoria_logs_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Event log service is not configured",
        )

    query_parts = ["log.event_name:*"]

    if service_tag:
        query_parts.append(f'log.service:"{service_tag}"')

    if username:
        query_parts.append(f'log.user:"{username}"')

    query = " AND ".join(query_parts)
    params = {"limit": limit or 100, "offset": offset or 0}

    if start_date:
        params["start"] = start_date.isoformat()

    if end_date:
        params["end"] = end_date.isoformat()

    data = query_logs(query, params)
    total = count_logs(query, params)

    meta = {"total": total, "limit": params["limit"], "offset": params["offset"], "count": len(data)}

    return {"data": data, "meta": meta}


@logs_router.post(
    "/events/signin",
    status_code=status.HTTP_201_CREATED,
    name="auth.user.signin",
    response_model=None,
)
async def log_user_signin():
    """Create a log event that a user signed in. Username is extracted from the JWT required to call this endpoint."""
    return status.HTTP_201_CREATED


@logs_router.post(
    "/events/signout",
    status_code=status.HTTP_201_CREATED,
    name="auth.user.signout",
    response_model=None,
)
async def log_user_signout():
    """Create a log event that a user signed out. Username is extracted from the JWT required to call this endpoint."""
    return status.HTTP_201_CREATED


@logs_router.get(
    "/logs/{analysis_id}",
    status_code=status.HTTP_200_OK,
    name="logs.analysis.live.get",
    response_model=AnalysisLogsResponse,
)
async def get_analysis_logs(
    analysis_id: Annotated[uuid.UUID, Path(description="UUID of the analysis.")],
):
    """Get the latest logs for both containers of an analysis (highest run number)."""
    settings = get_settings()
    if not settings.victoria_logs_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Log service is not configured",
        )

    container_names = _get_analysis_container_names(str(analysis_id))
    runs = _group_by_run(container_names)

    if not runs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No logs found for analysis {analysis_id}",
        )

    latest_run_num = max(runs)
    latest = runs[latest_run_num]

    return {
        "analysis_id": analysis_id,
        "run_number": latest_run_num,
        "nginx_logs": _query_pod_logs(latest["nginx"]) if "nginx" in latest else [],
        "analysis_logs": _query_pod_logs(latest["analysis"]) if "analysis" in latest else [],
    }


@logs_router.get(
    "/history/{analysis_id}",
    status_code=status.HTTP_200_OK,
    name="logs.analysis.history.get",
    response_model=AnalysisLogHistoryResponse,
)
async def get_analysis_log_history(
    analysis_id: Annotated[uuid.UUID, Path(description="UUID of the analysis.")],
):
    """Get logs for all runs of an analysis, sorted by run number ascending."""
    settings = get_settings()
    if not settings.victoria_logs_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Log service is not configured",
        )

    container_names = _get_analysis_container_names(str(analysis_id))
    runs = _group_by_run(container_names)

    result_runs = []
    for run_num in sorted(runs):
        run = runs[run_num]
        result_runs.append(
            {
                "run_number": run_num,
                "nginx_logs": _query_pod_logs(run["nginx"]) if "nginx" in run else [],
                "analysis_logs": _query_pod_logs(run["analysis"]) if "analysis" in run else [],
            }
        )

    return {"analysis_id": analysis_id, "runs": result_runs}
