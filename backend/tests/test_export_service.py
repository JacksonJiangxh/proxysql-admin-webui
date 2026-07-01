"""Unit tests for ExportService: CSV, JSON, and Response generation."""

import json
from app.services.export_service import export_service


class TestExportService:
    """Tests for the ExportService (pure functions, no DB/HTTP needed)."""

    def test_to_csv_basic(self):
        """to_csv produces valid CSV with header + data rows."""
        rows = [
            {"name": "Alice", "age": 30, "city": "NYC"},
            {"name": "Bob", "age": 25, "city": "LA"},
        ]
        csv_str = export_service.to_csv(rows)
        lines = csv_str.strip().split("\r\n")
        assert len(lines) == 3
        assert "name,age,city" in lines[0]
        assert "Alice" in lines[1]
        assert "Bob" in lines[2]

    def test_to_csv_empty(self):
        """to_csv returns empty string for empty input."""
        assert export_service.to_csv([]) == ""

    def test_to_csv_special_values(self):
        """to_csv handles None, special chars, and numbers."""
        rows = [
            {"col": None, "val": 0},
            {"col": "hello, world", "val": -1},
        ]
        csv_str = export_service.to_csv(rows)
        lines = csv_str.strip().split("\r\n")
        assert len(lines) == 3

    def test_to_json_pretty(self):
        """to_json with indent=True produces formatted JSON."""
        rows = [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]
        json_str = export_service.to_json(rows, indent=True)
        assert json_str.startswith("[\n")
        assert "  " in json_str
        parsed = json.loads(json_str)
        assert len(parsed) == 2
        assert parsed[0]["a"] == 1

    def test_to_json_compact(self):
        """to_json with indent=False produces compact JSON."""
        rows = [{"a": 1, "b": "x"}]
        json_str = export_service.to_json(rows, indent=False)
        assert "\n" not in json_str
        parsed = json.loads(json_str)
        assert len(parsed) == 1

    def test_to_json_unicode(self):
        """to_json preserves Unicode characters (ensure_ascii=False)."""
        rows = [{"name": "张三", "city": "北京"}]
        json_str = export_service.to_json(rows)
        assert "张三" in json_str
        assert "北京" in json_str

    def test_create_response_csv(self):
        """create_response returns Response with CSV content type."""
        resp = export_service.create_response(
            "a,b\n1,2", format="csv", filename="test"
        )
        assert resp.media_type == "text/csv; charset=utf-8"
        assert "attachment" in resp.headers["content-disposition"]
        assert "test.csv" in resp.headers["content-disposition"]

    def test_create_response_json(self):
        """create_response returns Response with JSON content type."""
        resp = export_service.create_response(
            '{"k":"v"}', format="json", filename="data"
        )
        assert resp.media_type == "application/json; charset=utf-8"
        assert "data.json" in resp.headers["content-disposition"]

    def test_create_response_unknown_format(self):
        """create_response falls back to text/plain for unknown format."""
        resp = export_service.create_response(
            "content", format="xml", filename="file"
        )
        assert resp.media_type == "text/plain"
