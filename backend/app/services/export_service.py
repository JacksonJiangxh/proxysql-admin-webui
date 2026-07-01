"""Data export service: CSV and JSON format generation.""" 
import csv
import io
import json
from typing import Any, Optional


class ExportService:
    """Generates CSV and JSON formatted data for download."""

    @staticmethod
    def to_csv(rows: list[dict[str, Any]], filename: str = "export") -> str:
        """Convert a list of dicts to CSV string."""
        if not rows:
            return ""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(rows[0].keys())
        for row in rows:
            writer.writerow(row.values())
        return output.getvalue()

    @staticmethod
    def to_json(rows: list[dict[str, Any]], indent: bool = True) -> str:
        """Convert a list of dicts to JSON string."""
        return json.dumps(rows, default=str, indent=2 if indent else None, ensure_ascii=False)

    @staticmethod
    def create_response(
        data: str,
        format: str,
        filename: str = "export",
    ):
        """Create a FastAPI Response with appropriate content type and headers."""
        from fastapi.responses import Response
        media_types = {
            "csv": "text/csv; charset=utf-8",
            "json": "application/json; charset=utf-8",
        }
        media = media_types.get(format, "text/plain")
        return Response(
            content=data.encode("utf-8") if isinstance(data, str) else data,
            media_type=media,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}.{format}"',
            },
        )


export_service = ExportService()
