"""Schema introspection service for ProxySQL tables."""
import re
from typing import Optional

from app.services.proxysql import proxysql_service
from app.utils.helpers import quote_ident, split_commas


class SchemaService:
    """Introspects and parses ProxySQL table schemas."""

    async def get_table_schema(
        self, host: str, port: int, user: str, password: str,
        database: str, table_name: str,
    ) -> dict:
        """Get full table schema including parsed columns, PKs, and constraints."""
        # Validate identifiers to prevent SQL injection
        try:
            safe_db = quote_ident(database)
            safe_table = quote_ident(table_name)
        except ValueError as e:
            raise ValueError(f"Invalid identifier: {e}")

        create_result = await proxysql_service.execute_query(
            host, port, user, password,
            f"SHOW CREATE TABLE {safe_db}.{safe_table}"
        )

        if not create_result:
            raise ValueError(f"Table {table_name} not found")

        # Extract SQL text from result
        sql_text = list(create_result[0].values())[0] if isinstance(create_result[0], dict) else create_result[0][1]

        columns = self._parse_columns(sql_text)
        primary_keys = self._parse_primary_keys(sql_text)
        check_constraints = self._parse_check_constraints(sql_text)

        return {
            "table_name": table_name,
            "database": database,
            "columns": columns,
            "primary_keys": primary_keys,
            "check_constraints": check_constraints,
            "create_sql": sql_text,
        }

    def _parse_columns(self, create_sql: str) -> list[dict]:
        """Parse column definitions from CREATE TABLE SQL."""
        start = create_sql.find('(')
        end = create_sql.rfind(')')
        if start == -1 or end == -1:
            return []
        body = create_sql[start + 1:end]

        columns = []
        for part in split_commas(body):
            part = part.strip()
            if not part or part.upper().startswith(('PRIMARY', 'UNIQUE', 'CHECK', 'FOREIGN', 'CONSTRAINT')):
                continue

            match = re.match(r'[`"\[]?(\w+)[`"\]]?\s+(\w+(?:\([^)]+\))?)', part)
            if not match:
                continue

            col_name = match.group(1)
            col_type = match.group(2).upper()
            rest = part[match.end():]
            nullable = 'NOT NULL' not in rest.upper()

            default_match = re.search(r"DEFAULT\s+('[^']*'|\"[^\"]*\"|\w+)", rest, re.IGNORECASE)
            default_value = default_match.group(1).strip("'\"") if default_match else None

            columns.append({
                "name": col_name,
                "type": col_type,
                "nullable": nullable,
                "default": default_value,
            })

        return columns

    def _parse_primary_keys(self, create_sql: str) -> list[str]:
        """Parse primary key columns from CREATE TABLE SQL."""
        # Block form: PRIMARY KEY (col1, col2)
        match = re.search(r'PRIMARY\s+KEY\s*\(([^)]+)\)', create_sql, re.IGNORECASE)
        if match:
            return [c.strip().strip('`"[]') for c in match.group(1).split(',')]

        # Inline form: col TYPE PRIMARY KEY
        inline_keys = []
        start = create_sql.find('(')
        end = create_sql.rfind(')')
        if start == -1 or end == -1:
            return inline_keys
        body = create_sql[start + 1:end]
        for part in split_commas(body):
            if re.search(r'\bPRIMARY\s+KEY\b(?!\s*\()', part, re.IGNORECASE):
                m = re.match(r'[`"\[]?(\w+)[`"\]]?', part.strip())
                if m:
                    inline_keys.append(m.group(1))
        return inline_keys

    def _parse_check_constraints(self, create_sql: str) -> dict:
        """Parse CHECK constraints from CREATE TABLE SQL."""
        constraints = {}
        # Iterate through column definitions using split_commas
        start = create_sql.find('(')
        end = create_sql.rfind(')')
        if start == -1 or end == -1:
            return constraints
        body = create_sql[start + 1:end]

        for part in split_commas(body):
            part = part.strip()
            if not part:
                continue
            # Look for CHECK ( expr ) with balanced parens
            check_match = re.search(r'\bCHECK\s*\(', part, re.IGNORECASE)
            if not check_match:
                continue
            # Extract column name (first word)
            col_match = re.match(r'[`"\[]?(\w+)[`"\]]?', part)
            if not col_match:
                continue
            col_name = col_match.group(1)
            if col_name.upper() in ('PRIMARY', 'UNIQUE', 'CONSTRAINT', 'FOREIGN', 'CHECK'):
                continue
            # Extract CHECK expression using balanced paren matching
            check_start = check_match.end()  # position after 'CHECK('
            depth = 1
            expr_end = check_start
            while expr_end < len(part) and depth > 0:
                if part[expr_end] == '(':
                    depth += 1
                elif part[expr_end] == ')':
                    depth -= 1
                expr_end += 1
            if depth == 0:
                constraints[col_name] = part[check_start:expr_end - 1].strip()

        return constraints


schema_service = SchemaService()
