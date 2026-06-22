"""Tests for password policy validation."""
import pytest
from app.utils.password_policy import (
    validate_password,
    PasswordValidationError,
    is_common_password,
)


class TestPasswordValidation:
    """Test password policy validation."""

    def test_valid_password_accepted(self):
        """Test that a valid password passes all checks."""
        # Should not raise
        validate_password("MySecureP@ss1")

    def test_too_short_password_rejected(self):
        """Test that passwords shorter than minimum length are rejected."""
        with pytest.raises(PasswordValidationError) as exc_info:
            validate_password("Ab1")
        assert "at least" in str(exc_info.value).lower()
        assert "8" in str(exc_info.value)

    def test_no_uppercase_rejected(self):
        """Test that passwords without uppercase are rejected."""
        with pytest.raises(PasswordValidationError) as exc_info:
            validate_password("mypassword1")
        assert "uppercase" in str(exc_info.value).lower()

    def test_no_lowercase_rejected(self):
        """Test that passwords without lowercase are rejected."""
        with pytest.raises(PasswordValidationError) as exc_info:
            validate_password("MYPASSWORD1")
        assert "lowercase" in str(exc_info.value).lower()

    def test_no_digit_rejected(self):
        """Test that passwords without digits are rejected."""
        with pytest.raises(PasswordValidationError) as exc_info:
            validate_password("MyPassword")
        assert "digit" in str(exc_info.value).lower()

    def test_exactly_minimum_length(self):
        """Test that passwords at exactly the minimum length are accepted."""
        validate_password("Abcdef1!")  # 8 chars

    def test_longer_password(self):
        """Test that longer passwords are accepted."""
        validate_password("ThisIsAVeryLongPassword123!@#")

    def test_empty_password_rejected(self):
        """Test that empty passwords are rejected."""
        with pytest.raises(PasswordValidationError):
            validate_password("")

    def test_whitespace_only_rejected(self):
        """Test that whitespace-only passwords are rejected."""
        with pytest.raises(PasswordValidationError):
            validate_password("        ")

    def test_password_with_special_chars(self):
        """Test that passwords with special characters are accepted."""
        validate_password("MyP@ssw0rd!#$%^&*()")


class TestCommonPasswordBlocklist:
    """Test common password rejection."""

    def test_password_blocked(self):
        """Test that 'password123' is blocked."""
        assert is_common_password("password123") is True

    def test_admin_blocked(self):
        """Test that 'admin123' is blocked."""
        assert is_common_password("admin123") is True

    def test_12345678_blocked(self):
        """Test that '12345678' is blocked."""
        assert is_common_password("12345678") is True

    def test_qwerty_blocked(self):
        """Test that 'qwerty123' is blocked."""
        assert is_common_password("qwerty123") is True

    def test_letmein_blocked(self):
        """Test that 'letmein12' is blocked."""
        assert is_common_password("letmein12") is True

    def test_unique_password_not_blocked(self):
        """Test that a unique password is not in the blocklist."""
        assert is_common_password("XyZ!9kLm2#PqR") is False


class TestPasswordPolicyIntegration:
    """Integration-style tests for password validation in context."""

    def test_common_password_validates_but_blocked(self):
        """Test that a common password that meets complexity rules is still rejected."""
        # "Password1" meets complexity but is in common list
        with pytest.raises(PasswordValidationError) as exc_info:
            validate_password("Password1")
        assert "common" in str(exc_info.value).lower() or "blocklist" in str(exc_info.value).lower()

    def test_default_min_length_config(self):
        """Test the default minimum password length from settings."""
        from app.config import settings
        # Verify the setting exists and has a reasonable default
        assert hasattr(settings, 'SECURITY_MIN_PASSWORD_LENGTH')
        assert settings.SECURITY_MIN_PASSWORD_LENGTH >= 8

    def test_custom_min_length(self):
        """Test validation with a custom minimum length."""
        validate_password("Ab1defGh", min_length=6)  # 8 chars, min 6

    def test_custom_min_length_too_short(self):
        """Test rejection with a custom minimum length."""
        with pytest.raises(PasswordValidationError):
            validate_password("Ab1def", min_length=8)  # 6 chars, min 8
