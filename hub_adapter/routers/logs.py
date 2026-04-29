"""EPs for retrieving logged events."""

import datetime
import json
import logging
import re
import uuid
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Security, Path
from starlette import status

from hub_adapter.auth import verify_idp_token, jwtbearer, require_admin_role
from hub_adapter.constants import ServiceTag
from hub_adapter.dependencies import get_settings, make_log_hook
from hub_adapter.errors import require_victoria_logs
from hub_adapter.schemas.logs import (
    AnalysisLogHistoryResponse,
    AnalysisLogsResponse,
    ApiRequestCountResponse,
    EventLogResponse,
    LogQLQueryRequest,
    LogQLQueryResponse,
    NetStatResponse,
    NetStatRun,
    NetStatTotal,
)

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


def _execute_raw_query(query: str, params: dict | None = None) -> list[dict]:
    """Execute a LogQL query against VictoriaLogs and return raw parsed results."""
    settings = get_settings()
    query_data = {"query": query, **(params or {})}
    with httpx.Client(event_hooks={"response": [make_log_hook(ServiceTag.LOGS)]}) as client:
        resp = client.post(
            f"{settings.victoria_logs_url}/select/logsql/query",
            data=query_data,
        )
        resp.raise_for_status()
    logs = []
    for line in resp.text.strip().splitlines():
        if line:
            logs.append(json.loads(line))
    return logs


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


def _query_pod_logs(
    container_name: str,
    start_date: datetime.datetime | None = None,
    end_date: datetime.datetime | None = None,
    limit: int | None = 1000,
    offset: int = 0,
) -> list[dict]:
    """Return log lines for a specific container, sorted oldest-first."""
    settings = get_settings()
    query = f'kubernetes.container_name:"{container_name}"'
    query_data: dict = {
        "query": (f"{query} | fields _time, _msg, level, log.error | sort by (_time)"),
        "limit": limit,
    }
    if offset:
        query_data["offset"] = offset

    if start_date:
        query_data["start"] = start_date.isoformat()

    if end_date:
        query_data["end"] = end_date.isoformat()

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
            log_entry = {
                "timestamp": entry.get("_time", ""),
                "message": entry.get("_msg", ""),
                "level": entry.get("level") or None,
            }
            if stacktrace := entry.get("log.error"):
                log_entry["stacktrace"] = stacktrace
            logs.append(log_entry)
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
@require_victoria_logs
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
@require_victoria_logs
async def get_analysis_logs(
    analysis_id: Annotated[uuid.UUID, Path(description="UUID of the analysis.")],
    start_date: Annotated[
        datetime.datetime | None,
        Query(description="Filter logs from this timestamp using ISO8601 format"),
    ] = None,
    end_date: Annotated[
        datetime.datetime | None,
        Query(description="Filter logs up to this timestamp using ISO8601 format"),
    ] = None,
    limit: Annotated[int | None, Query(description="Maximum number of log lines to return per container")] = 1000,
    offset: Annotated[int | None, Query(description="Number of log lines to skip per container")] = 0,
):
    """Get the latest logs for both containers of an analysis (highest run number)."""
    container_names = _get_analysis_container_names(str(analysis_id))
    runs = _group_by_run(container_names)

    if not runs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No logs found for analysis {analysis_id}",
        )

    latest_run_num = max(runs)
    latest = runs[latest_run_num]

    pod_args = (start_date, end_date, limit, offset)
    return {
        "analysis_id": analysis_id,
        "run_number": latest_run_num,
        "nginx_logs": _query_pod_logs(latest["nginx"], *pod_args) if "nginx" in latest else [],
        "analysis_logs": _query_pod_logs(latest["analysis"], *pod_args) if "analysis" in latest else [],
    }


@logs_router.get(
    "/history/{analysis_id}",
    status_code=status.HTTP_200_OK,
    name="logs.analysis.history.get",
    response_model=AnalysisLogHistoryResponse,
)
@require_victoria_logs
async def get_analysis_log_history(
    analysis_id: Annotated[uuid.UUID, Path(description="UUID of the analysis.")],
    start_date: Annotated[
        datetime.datetime | None,
        Query(description="Filter logs from this timestamp using ISO8601 format"),
    ] = None,
    end_date: Annotated[
        datetime.datetime | None,
        Query(description="Filter logs up to this timestamp using ISO8601 format"),
    ] = None,
    limit: Annotated[int, Query(description="Maximum number of log lines to return per container")] = 1000,
    offset: Annotated[int, Query(description="Number of log lines to skip per container")] = 0,
):
    """Get logs for all runs of an analysis, sorted by run number ascending."""
    container_names = _get_analysis_container_names(str(analysis_id))
    runs = _group_by_run(container_names)

    pod_args = (start_date, end_date, limit, offset)
    result_runs = []
    for run_num in sorted(runs):
        run = runs[run_num]
        result_runs.append(
            {
                "run_number": run_num,
                "nginx_logs": _query_pod_logs(run["nginx"], *pod_args) if "nginx" in run else [],
                "analysis_logs": _query_pod_logs(run["analysis"], *pod_args) if "analysis" in run else [],
            }
        )

    return {"analysis_id": analysis_id, "runs": result_runs}


def _parse_netstats_container(container_name: str) -> tuple[str, int]:
    """Strip the 'net-stats-analysis-' prefix and split on the last dash to get (analysis_id_str, run_number)."""
    prefix = "net-stats-analysis-"
    if not container_name.startswith(prefix):
        raise ValueError(f"Unexpected container name format: {container_name!r}")
    remainder = container_name[len(prefix) :]
    analysis_id_str, _, run_str = remainder.rpartition("-")
    if not analysis_id_str or not run_str.isdigit():
        raise ValueError(f"Cannot parse run number from container name: {container_name!r}")
    return analysis_id_str, int(run_str)


@logs_router.get(
    "/netstats",
    status_code=status.HTTP_200_OK,
    response_model=NetStatResponse,
    name="logs.netstats.get",
)
@require_victoria_logs
async def get_netstats(
    analysis_id: Annotated[uuid.UUID | None, Query(description="Filter by analysis UUID")] = None,
    start_date: Annotated[
        datetime.datetime | None,
        Query(description="Filter by start date using ISO8601 format"),
    ] = None,
    end_date: Annotated[
        datetime.datetime | None,
        Query(description="Filter by end date using ISO8601 format"),
    ] = None,
    limit: Annotated[int, Query(description="Maximum number of raw log entries to return")] = 1000,
):
    """Retrieve network traffic statistics from netstats log events."""
    query_parts = ['log.event_name:"netstats.analysis.traffic"']
    if analysis_id is not None:
        query_parts.append(f'kubernetes.container_name:~"net-stats-analysis-{str(analysis_id)}-"')
    base_query = " AND ".join(query_parts)

    fields = "_time, kubernetes.container_name, kubernetes.pod_name, log.bytes_in, log.bytes_out"
    logsql_query = f"{base_query} | fields {fields}"

    params: dict = {"limit": limit}
    if start_date:
        params["start"] = start_date.isoformat()
    if end_date:
        params["end"] = end_date.isoformat()

    raw_logs = _execute_raw_query(logsql_query, params)
    total = count_logs(base_query, params)

    totals: dict[str, NetStatTotal] = {}
    for entry in raw_logs:
        container_name = entry.get("kubernetes.container_name", "")
        try:
            analysis_id_str, run_number = _parse_netstats_container(container_name)
            entry_analysis_id = uuid.UUID(analysis_id_str)

        except (ValueError, AttributeError):
            logger.warning(f"Skipping netstats entry with unparseable container name: {container_name}")
            continue

        raw_time = entry.get("_time", "")
        run = NetStatRun(
            timestamp=datetime.datetime.fromisoformat(raw_time) if raw_time else datetime.datetime.min,
            container=container_name,
            run_number=run_number,
            pod=entry.get("kubernetes.pod_name", ""),
            bytes_in=int(entry.get("log.bytes_in") or 0),
            bytes_out=int(entry.get("log.bytes_out") or 0),
        )

        key = str(entry_analysis_id)
        if key not in totals:
            totals[key] = NetStatTotal(analysis_id=entry_analysis_id, bytes_in=0, bytes_out=0, runs=[])
        totals[key].runs.append(run)
        totals[key].bytes_in += run.bytes_in
        totals[key].bytes_out += run.bytes_out

    data = list(totals.values())
    meta = {"total": total, "limit": limit, "offset": 0, "count": len(data)}
    return {"data": data, "meta": meta}


@logs_router.post(
    "/logs/query",
    status_code=status.HTTP_200_OK,
    name="logs.query.raw",
    response_model=LogQLQueryResponse,
    dependencies=[Depends(require_admin_role)],
)
@require_victoria_logs
async def raw_log_query(body: LogQLQueryRequest):
    """Execute a raw LogQL query against VictoriaLogs. Admin only."""
    params: dict = {"limit": body.limit, "offset": body.offset}
    if body.start:
        params["start"] = body.start.isoformat()
    if body.end:
        params["end"] = body.end.isoformat()

    data = _execute_raw_query(body.query, params)
    total = count_logs(body.query, params)

    meta = {"total": total, "limit": body.limit, "offset": body.offset, "count": len(data)}
    return {"data": data, "meta": meta}


@logs_router.get(
    "/requests",
    status_code=status.HTTP_200_OK,
    response_model=ApiRequestCountResponse,
    name="logs.requests.get",
)
@require_victoria_logs
async def get_api_requests(
    start_date: Annotated[
        datetime.datetime | None,
        Query(description="Filter requests from this timestamp using ISO8601 format"),
    ] = None,
    end_date: Annotated[
        datetime.datetime | None,
        Query(description="Filter requests up to this timestamp using ISO8601 format"),
    ] = None,
    endpoint: Annotated[
        str | None,
        Query(description="Filter breakdown to paths starting with this prefix"),
    ] = None,
    method: Annotated[
        str | None,
        Query(description="Filter breakdown to a specific HTTP method (e.g. GET, POST, DELETE)"),
    ] = None,
):
    """Get total API request count and a per-endpoint breakdown grouped by HTTP method and path."""
    logsql_query = r"""log.logger:"uvicorn.access" | extract '<_> "<method> <path> HTTP/<_>" <status>' | stats by (method, path) count() as requests"""
    params: dict = {}
    if start_date:
        params["start"] = start_date.isoformat()
    if end_date:
        params["end"] = end_date.isoformat()

    raw = _execute_raw_query(logsql_query, params)
    method_filter = method.upper() if method else None

    by_path: dict[str, dict[str, int]] = {}
    for entry in raw:
        req_method = entry.get("method", "")
        base_path = entry.get("path", "").split("?")[0]
        count = int(entry.get("requests", 0))
        by_path.setdefault(base_path, {})
        by_path[base_path][req_method] = by_path[base_path].get(req_method, 0) + count

    data: dict[str, dict[str, int]] = {}
    for path in sorted(by_path):
        if endpoint is not None and not path.startswith(endpoint):
            continue
        methods = by_path[path]
        if method_filter is not None:
            if method_filter not in methods:
                continue
            methods = {method_filter: methods[method_filter]}
        data[path] = {**methods, "total": sum(methods.values())}

    return {"total": sum(v["total"] for v in data.values()), "data": data}
