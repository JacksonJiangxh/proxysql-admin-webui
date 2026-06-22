"""Password policy validation utilities.

Enforces password complexity requirements and blocks common passwords.
"""
import re
from app.config import settings


# Common password blocklist - these are the most frequently used
# passwords that should always be rejected regardless of complexity.
_COMMON_PASSWORDS: set[str] = {
    "password", "password1", "password12", "password123",
    "admin", "admin123", "administrator",
    "12345678", "123456789", "1234567890",
    "qwerty123", "qwerty1234",
    "letmein", "letmein12", "letmein123",
    "welcome", "welcome1", "welcome12",
    "monkey", "dragon", "master",
    "abc123", "123123", "passw0rd",
    "changeme", "changeme123",
    "iloveyou", "trustno1",
    "sunshine", "princess", "football",
    "Password1", "Password123",
    "Admin123", "Qwerty123",
    "P@ssw0rd", "P@ssword1",
    "proxyweb", "proxyweb1", "proxysql", "proxysql1",
}


class PasswordValidationError(ValueError):
    """Raised when a password fails policy validation."""
    pass


def is_common_password(password: str) -> bool:
    """Check if a password is in the common password blocklist.

    Comparison is case-insensitive.
    """
    return password.lower() in _COMMON_PASSWORDS


def validate_password(
    password: str,
    min_length: int | None = None,
    check_common: bool = True,
) -> None:
    """Validate a password against the configured policy.

    Policy requirements:
    - Minimum length (configurable via SECURITY_MIN_PASSWORD_LENGTH, default 8)
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - Not in the common password blocklist

    Args:
        password: The password to validate.
        min_length: Override the minimum length. Uses settings if not provided.
        check_common: Whether to check against the common password blocklist.

    Raises:
        PasswordValidationError: If the password fails any check.
    """
    if min_length is None:
        min_length = getattr(settings, 'SECURITY_MIN_PASSWORD_LENGTH', 8)

    # Check minimum length
    if len(password) < min_length:
        raise PasswordValidationError(
            f"Password must be at least {min_length} characters long"
        )

    # Check for at least one uppercase letter
    if not re.search(r'[A-Z]', password):
        raise PasswordValidationError(
            "Password must contain at least one uppercase letter"
        )

    # Check for at least one lowercase letter
    if not re.search(r'[a-z]', password):
        raise PasswordValidationError(
            "Password must contain at least one lowercase letter"
        )

    # Check for at least one digit
    if not re.search(r'[0-9]', password):
        raise PasswordValidationError(
            "Password must contain at least one digit"
        )

    # Check against common password blocklist
    if check_common and is_common_password(password):
        raise PasswordValidationError(
            "This password is too common and easily guessed. Please choose a stronger password."
        )
