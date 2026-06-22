"""SQL sanitization utilities for the query console.

Provides whitelist-based SQL identifier validation and dangerous-pattern
detection to prevent SQL injection and accidental destructive operations.
"""
import re
from enum import Enum
from typing import Optional


class SQLSeverity(str, Enum):
    """Severity level of a SQL validation result."""
    OK = "ok"
    WARNING = "warning"
    BLOCKED = "blocked"


# Destructive SQL patterns that should be blocked for non-admin users.
# These are patterns that would DROP, TRUNCATE, ALTER table structure,
# or otherwise cause data loss.
DANGEROUS_PATTERNS = [
    re.compile(r"\bDROP\s+(TABLE|DATABASE|SCHEMA|VIEW|INDEX|FUNCTION|PROCEDURE|TRIGGER)\b", re.IGNORECASE),
    re.compile(r"\bTRUNCATE\s+(TABLE\s+)?", re.IGNORECASE),
    re.compile(r"\bALTER\s+TABLE\b", re.IGNORECASE),
    re.compile(r"\bDELETE\s+FROM\s+\S+", re.IGNORECASE),
    re.compile(r"\bRENAME\s+TABLE\b", re.IGNORECASE),
    re.compile(r"\bDETACH\s+DATABASE\b", re.IGNORECASE),
]

# Patterns that are potentially dangerous and should trigger a warning
WARNING_PATTERNS = [
    re.compile(r"\bCREATE\s+TABLE\b", re.IGNORECASE),
    re.compile(r"\bINSERT\s+INTO\b", re.IGNORECASE),
    re.compile(r"\bUPDATE\s+\S+\s+SET\b", re.IGNORECASE),
    re.compile(r"\bREPLACE\s+INTO\b", re.IGNORECASE),
]

# Safe identifier characters - only alphanumeric and underscore
IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def validate_identifier(name: str, context: str = "identifier") -> str:
    """Validate a SQL identifier against a strict whitelist.

    Only allows alphanumeric characters and underscores, must start
    with a letter or underscore.

    Args:
        name: The identifier to validate.
        context: Human-readable context for error messages.

    Returns:
        The validated identifier.

    Raises:
        ValueError: If the identifier contains dangerous characters.
    """
    if not name or not isinstance(name, str):
        raise ValueError(f"Invalid {context}: must be a non-empty string")

    if not IDENTIFIER_RE.match(name):
        raise ValueError(
            f"Invalid {context} '{name}': only alphanumeric characters "
            f"and underscores are allowed, must start with a letter or underscore"
        )

    return name


def check_sql_danger(sql: str, is_admin: bool = False) -> dict:
    """Check a SQL string for dangerous patterns.

    Args:
        sql: The SQL statement to check.
        is_admin: Whether the current user has admin role (admins bypass blocks).

    Returns:
        A dict with keys:
        - severity: SQLSeverity value (ok, warning, blocked)
        - blocked: bool, True if the statement should be blocked
        - message: str, explanation of the result
        - matched_pattern: Optional[str], the pattern that was matched
    """
    if not sql or not sql.strip():
        return {
            "severity": SQLSeverity.OK,
            "blocked": False,
            "message": "Empty SQL statement",
            "matched_pattern": None,
        }

    # Check blocked patterns first
    for pattern in DANGEROUS_PATTERNS:
        match = pattern.search(sql)
        if match:
            if is_admin:
                return {
                    "severity": SQLSeverity.WARNING,
                    "blocked": False,
                    "message": f"Destructive operation '{match.group(0).strip().upper()}' detected. Proceed with caution.",
                    "matched_pattern": match.group(0).strip(),
                }
            return {
                "severity": SQLSeverity.BLOCKED,
                "blocked": True,
                "message": (
                    f"Destructive operation '{match.group(0).strip().upper()}' is not allowed. "
                    f"Only admin users can execute DDL/DML that modifies schema or deletes data."
                ),
                "matched_pattern": match.group(0).strip(),
            }

    # Check warning patterns
    for pattern in WARNING_PATTERNS:
        match = pattern.search(sql)
        if match:
            return {
                "severity": SQLSeverity.WARNING,
                "blocked": False,
                "message": f"Write operation '{match.group(0).strip().upper()}' detected.",
                "matched_pattern": match.group(0).strip(),
            }

    return {
        "severity": SQLSeverity.OK,
        "blocked": False,
        "message": "SQL statement looks safe",
        "matched_pattern": None,
    }


def sanitize_sql(sql: str, is_admin: bool = False) -> tuple[str, Optional[str]]:
    """Validate and sanitize a user-submitted SQL statement.

    Returns:
        Tuple of (sanitized_sql, error_message).
        If error_message is not None, the SQL should be rejected.
    """
    # Trim whitespace
    sql = sql.strip()

    if not sql:
        return sql, "SQL statement cannot be empty"

    # Check length (prevent resource exhaustion)
    if len(sql) > 10000:
        return sql, "SQL statement exceeds maximum length of 10,000 characters"

    # Check for dangerous patterns
    result = check_sql_danger(sql, is_admin)
    if result["blocked"]:
        return sql, result["message"]

    return sql, None
