"""Base class for read-only query-based wizards (monitoring & diagnostics).

Unlike ``BaseWizard`` which generates INSERT/UPDATE SQL, ``QueryWizard``
runs SELECT queries against ProxySQL stats tables and returns the result
rows for the frontend to render as tables/charts.
"""
from abc import abstractmethod
from typing import Any

from app.services.wizard_engine import BaseWizard
from app.services.proxysql import proxysql_service


class QueryWizard(BaseWizard):
    """Base class for read-only monitoring/diagnostic wizards.

    Subclasses implement :meth:`generate_queries` to return a mapping of
    ``{label: sql}`` pairs. The ``execute`` method runs each query and
    returns the collected results. These wizards never modify state, so
    ``auto_apply`` / ``auto_save`` are ignored.
    """

    @abstractmethod
    def generate_queries(self, fields: dict) -> dict[str, str]:
        """Return ``{result_key: sql_query}`` mapping for execution."""
        ...

    # Query wizards don't use generate_sql; provide a no-op so the ABC
    # contract is satisfied.
    def generate_sql(self, fields: dict) -> list[str]:
        return list(self.generate_queries(fields).values())

    async def execute(
        self,
        host: str, port: int, user: str, password: str,
        fields: dict,
        auto_apply: bool = False,
        auto_save: bool = False,
    ) -> dict:
        """Execute the read-only queries and return collected results."""
        errors = self.validate(fields)
        if errors:
            return {"ok": False, "errors": errors}

        queries = self.generate_queries(fields)
        results: dict[str, Any] = {}
        executed_sql: list[str] = []
        all_ok = True

        for key, sql in queries.items():
            try:
                rows = await proxysql_service.execute_query(
                    host, port, user, password, sql
                )
                results[key] = rows
                executed_sql.append(sql)
            except Exception as e:
                results[key] = {"error": str(e)}
                executed_sql.append(sql)
                all_ok = False

        return {
            "ok": True,
            "wizard_id": self.definition.id,
            "wizard_name": self.definition.name,
            "executed_sql": executed_sql,
            "query_results": results,
            "all_succeeded": all_ok,
        }

    def preview_sql(self, fields: dict) -> dict:
        """Preview the queries that would be executed."""
        errors = self.validate(fields)
        if errors:
            return {"ok": False, "errors": errors}

        queries = self.generate_queries(fields)
        return {
            "ok": True,
            "wizard_id": self.definition.id,
            "wizard_name": self.definition.name,
            "sql_preview": list(queries.values()),
            "auto_apply_sql": None,
            "affected_modules": [],
            "warnings": ["This is a read-only query wizard; no data is modified."],
        }
