"""Data export API endpoints — download query results / table data as CSV or JSON.""" 
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional

from app.middleware import get_current_user
from app.schemas.response import RESPONSE_AUTH, HTTPError
from app.services.export_service import export_service
from app.services.query_engine import query_engine
from app.utils.db_helpers import get_proxysql_credentials

router = APIRouter(tags=["Export"])


@router.post(
    "/{server_id}/query-result",
    responses={
        200: {
            "description": "Query results as downloadable file.",
            "content": {
                "text/csv": {},
                "application/json": {},
            },
        },
        400: {"description": "Query execution failed.", "model": HTTPError},
        404: {"description": "Query returned no rows.", "model": HTTPError},
        **RESPONSE_AUTH,
    },
    summary="Export query result",
    description="Execute a SQL query and download results as CSV or JSON file. "
                "Requires admin or operator role.",
)
async def export_query_result(
    server_id: str,
    sql: str = Query(..., description="SQL query to execute for export."),
    format: str = Query(
        "csv",
        regex="^(csv|json)$",
        description="Export format: 'csv' or 'json'.",
    ),
    user=Depends(get_current_user),
):
    """Execute a query and return results as a downloadable file."""
    host, port, admin_user, password = await get_proxysql_credentials(server_id)

    try:
        result = await query_engine.execute(
            host, port, admin_user, password,
            sql=sql,
            target="admin",
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Query failed: {str(e)}")

    rows = result.get("rows", [])
    if not rows:
        raise HTTPException(status_code=404, detail="Query returned no rows to export")

    if format == "csv":
        data = export_service.to_csv(rows)
    else:
        data = export_service.to_json(rows)

    return export_service.create_response(data, format, filename="query_export")


@router.get(
    "/{server_id}/table/{table_name}",
    responses={
        200: {
            "description": "Table data as downloadable file.",
            "content": {
                "text/csv": {},
                "application/json": {},
            },
        },
        400: {"description": "Export failed — ProxySQL error.", "model": HTTPError},
        404: {"description": "Table is empty or does not exist.", "model": HTTPError},
        **RESPONSE_AUTH,
    },
    summary="Export table data",
    description="Download all rows from a ProxySQL config table in CSV or JSON format.",
)
async def export_table_data(
    server_id: str,
    table_name: str,
    format: str = Query(
        "csv",
        regex="^(csv|json)$",
        description="Export format: 'csv' or 'json'.",
    ),
    layer: str = Query(
        "memory",
        regex="^(memory|runtime|disk|stats|monitor)$",
        description="Config layer: memory, runtime, disk, stats, or monitor.",
    ),
    user=Depends(get_current_user),
):
    """Export all rows from a ProxySQL config table."""
    host, port, admin_user, password = await get_proxysql_credentials(server_id)

    db_map = {
        "memory": "main",
        "runtime": "main",
        "disk": "disk",
        "stats": "main",
        "monitor": "monitor",
    }
    database = db_map.get(layer, "main")
    actual_table = f"runtime_{table_name}" if layer == "runtime" else table_name

    try:
        rows = await query_engine.execute(
            host, port, admin_user, password,
            sql=f"SELECT * FROM {database}.{actual_table}",
            target="admin",
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Export failed: {str(e)}")

    rows_list = rows.get("rows", [])
    if not rows_list:
        raise HTTPException(status_code=404, detail="Table is empty or does not exist")

    if format == "csv":
        data = export_service.to_csv(rows_list)
    else:
        data = export_service.to_json(rows_list)

    safe_name = f"{table_name}_{layer}"
    return export_service.create_response(data, format, filename=safe_name)
