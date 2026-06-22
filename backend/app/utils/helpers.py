"""General utility functions."""
import json
import re
from typing import Any


def row_hash(row: dict) -> str:
    """Compute a deterministic hash for a row dict."""
    return json.dumps(row, sort_keys=True, default=str)


def split_commas(text: str) -> list[str]:
    """Split text by commas, respecting nested parentheses."""
    parts = []
    depth = 0
    current = ''
    for ch in text:
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


# Whitelist of characters allowed inside a SQL identifier. ProxySQL table /
# column names are alphanumeric plus underscore; rejecting anything else keeps
# injection attempts (backticks, quotes, semicolons, comments) out.
_IDENT_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


def quote_ident(identifier: str) -> str:
    """Quote a SQL identifier safely with backticks.

    Unlike the previous implementation (which only stripped backticks), this
    validates the identifier against a strict whitelist and rejects anything
    that looks like an injection attempt. Raises ``ValueError`` for unsafe
    input so callers fail closed instead of silently producing broken SQL.
    """
    if identifier is None:
        raise ValueError("identifier cannot be None")
    clean = identifier.strip()
    if not clean:
        raise ValueError("identifier cannot be empty")
    if not _IDENT_RE.match(clean):
        raise ValueError(
            f"Invalid SQL identifier: {identifier!r}. "
            "Only letters, digits and underscores are allowed (must start with "
            "a letter or underscore)."
        )
    return f"`{clean}`"


def escape_like(value: str) -> str:
    """Escape special LIKE characters."""
    return value.replace('!', '!!').replace('%', '!%').replace('_', '!_')
