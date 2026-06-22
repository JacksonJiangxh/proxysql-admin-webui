"""C header file parser for ProxySQL table definitions.

Parses ProxySQL_Admin_Tables_Definitions.h and extracts
table DDL definitions for code generation.
"""
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Column:
    name: str
    raw_type: str
    nullable: bool = True
    default: Optional[str] = None
    autoincrement: bool = False
    is_primary_key: bool = False
    check_expression: Optional[str] = None
    check_values: list[str] = field(default_factory=list)

    @property
    def python_type(self) -> str:
        """Map SQL type to Python type."""
        t = self.raw_type.upper()
        if any(x in t for x in ['INT', 'INTEGER', 'BIGINT', 'SMALLINT', 'TINYINT']):
            return 'int'
        if any(x in t for x in ['DOUBLE', 'FLOAT', 'REAL', 'DECIMAL', 'NUMERIC']):
            return 'float'
        return 'str'

    @property
    def python_type_annotation(self) -> str:
        t = self.python_type
        if self.nullable:
            return f'Optional[{t}]'
        return t


@dataclass
class TableDef:
    macro_name: str
    table_name: str
    columns: list[Column] = field(default_factory=list)
    table_pks: list[str] = field(default_factory=list)
    is_view: bool = False
    sql: str = ""

    @property
    def is_readonly(self) -> bool:
        return (
            self.table_name.startswith('stats_') or
            self.table_name.startswith('runtime_') or
            self.is_view
        )

    @property
    def all_pk_columns(self) -> list[str]:
        pks = list(self.table_pks)
        for col in self.columns:
            if col.is_primary_key and col.name not in pks:
                pks.append(col.name)
        return pks

    @property
    def model_class_name(self) -> str:
        """Convert table name to PascalCase class name."""
        parts = self.table_name.split('_')
        return ''.join(p.capitalize() for p in parts)


def read_header(path: str) -> str:
    """Read a C header file, handling backslash line continuations."""
    with open(path, 'r') as f:
        lines = f.readlines()

    result = []
    continuation = ''
    for line in lines:
        stripped = line.rstrip('\n\r')
        if stripped.endswith('\\'):
            continuation += stripped[:-1]
        else:
            if continuation:
                result.append(continuation + stripped)
                continuation = ''
            else:
                result.append(stripped)

    return '\n'.join(result)


def extract_defines(text: str) -> dict[str, str]:
    """Extract #define macros from preprocessed C text."""
    pattern = r'^\s*#define\s+(\w+)\s+(.+?)\s*$'
    defines = {}
    for match in re.finditer(pattern, text, re.MULTILINE):
        name = match.group(1)
        value = match.group(2)
        defines[name] = value
    return defines


def _unquote(value: str) -> str:
    """Unquote a C string literal, handling adjacent strings."""
    # Remove surrounding quotes and handle adjacent string concatenation
    value = value.strip()
    # Pattern: "str1" "str2" -> str1str2
    parts = re.findall(r'"((?:[^"\\]|\\.)*)"', value)
    if parts:
        return ''.join(parts)
    return value


def resolve_defines(defines: dict[str, str]) -> dict[str, str]:
    """Resolve alias chains to get final SQL strings."""
    result = {}
    for name, value in defines.items():
        current = value.strip()
        visited = {name}
        while current in defines and current not in visited:
            visited.add(current)
            current = defines[current].strip()

        unquoted = _unquote(current)
        if unquoted.upper().startswith(('CREATE TABLE', 'CREATE VIEW')):
            result[name] = unquoted

    return result


def is_current_table(macro_name: str) -> bool:
    """Check if a macro represents a current (non-versioned) table definition."""
    # Filter out versioned macros like _V1_0, _V2_0_11, etc.
    if re.search(r'_[Vv]\d+(_\d+)*[a-z]?$', macro_name):
        return False

    # Must be a table/stats prefix
    valid_prefixes = [
        'ADMIN_SQLITE_TABLE_',
        'ADMIN_SQLITE_RUNTIME_',
        'STATS_SQLITE_TABLE_',
    ]
    return any(macro_name.startswith(p) for p in valid_prefixes)


def _split_column_defs(body: str) -> list[str]:
    """Split CREATE TABLE body by commas, respecting parentheses."""
    parts = []
    depth = 0
    current = ''
    for ch in body:
        if ch == '(':
            depth += 1
            current += ch
        elif ch == ')':
            depth -= 1
            current += ch
        elif ch == ',' and depth == 0:
            parts.append(current.strip())
            current = ''
        else:
            current += ch
    if current.strip():
        parts.append(current.strip())
    return parts


def _parse_check_expression(text: str) -> Optional[tuple[str, list[str]]]:
    """Parse a CHECK constraint expression and extract IN values."""
    # Find CHECK(...)
    match = re.search(r'CHECK\s*\((.+)\)', text, re.IGNORECASE)
    if not match:
        return None

    expr = match.group(1).strip()

    # Extract IN values: UPPER(col) IN ('A','B') or col IN (0,1)
    in_match = re.search(r"IN\s*\(([^)]+(?:\([^)]*\)[^)]*)*)\)", expr, re.IGNORECASE)
    if in_match:
        in_body = in_match.group(1)
        values = []
        for v in re.findall(r"'([^']*)'", in_body):
            values.append(v)
        return (expr, values)

    return (expr, [])


def parse_create_table(sql: str, macro_name: str) -> TableDef:
    """Parse a CREATE TABLE/VIEW SQL statement."""
    is_view = 'CREATE VIEW' in sql.upper()
    table_match = re.search(
        r'CREATE\s+(?:TABLE|VIEW)\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)',
        sql, re.IGNORECASE
    )
    if not table_match:
        raise ValueError(f"Cannot parse table name from: {sql[:80]}...")

    table_name = table_match.group(1)
    table_def = TableDef(
        macro_name=macro_name,
        table_name=table_name,
        is_view=is_view,
        sql=sql,
    )

    # Extract body
    start = sql.find('(')
    end = sql.rfind(')')
    if start == -1 or end == -1:
        return table_def

    body = sql[start + 1:end]

    for part in _split_column_defs(body):
        part = part.strip()
        if not part:
            continue

        upper = part.upper()

        # Table-level constraints
        if upper.startswith('PRIMARY KEY'):
            pk_match = re.search(r'PRIMARY\s+KEY\s*\(([^)]+)\)', part, re.IGNORECASE)
            if pk_match:
                table_def.table_pks = [
                    c.strip().strip('`"[]')
                    for c in pk_match.group(1).split(',')
                ]
            continue

        if upper.startswith(('UNIQUE', 'CONSTRAINT', 'FOREIGN', 'CHECK')):
            continue

        # Column definition
        col_match = re.match(r'[`"\[]?(\w+)[`"\]]?\s+(\w+(?:\([^)]+\))?)', part)
        if not col_match:
            continue

        col_name = col_match.group(1)
        col_type = col_match.group(2)
        rest = part[col_match.end():]

        column = Column(name=col_name, raw_type=col_type)
        column.nullable = 'NOT NULL' not in rest.upper()
        column.autoincrement = 'AUTOINCREMENT' in rest.upper()
        column.is_primary_key = bool(
            re.search(r'\bPRIMARY\s+KEY\b(?!\s*\()', rest, re.IGNORECASE)
        )

        # Default value
        default_match = re.search(
            r"DEFAULT\s+('[^']*'|\"[^\"]*\"|[+-]?\d+\.?\d*|\w+)",
            rest, re.IGNORECASE
        )
        if default_match:
            val = default_match.group(1).strip("'\"")
            try:
                column.default = int(val)
            except ValueError:
                try:
                    column.default = float(val)
                except ValueError:
                    column.default = val

        # CHECK constraint
        check_result = _parse_check_expression(rest)
        if check_result:
            column.check_expression, column.check_values = check_result

        table_def.columns.append(column)

    return table_def
