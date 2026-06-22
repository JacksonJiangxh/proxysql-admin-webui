"""Tests for security utilities."""
import pytest
from app.utils.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token,
    encrypt_credential, decrypt_credential,
    constant_time_compare,
)


def test_password_hash_and_verify():
    """Test password hashing and verification."""
    password = "my_secure_password"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("wrong_password", hashed)


def test_jwt_token_flow():
    """Test JWT token creation and decoding."""
    data = {"sub": "1", "username": "admin", "role": "admin"}
    access_token = create_access_token(data)
    assert access_token is not None

    decoded = decode_token(access_token)
    assert decoded is not None
    assert decoded["sub"] == "1"
    assert decoded["username"] == "admin"
    assert decoded["type"] == "access"


def test_jwt_refresh_token():
    """Test refresh token type."""
    data = {"sub": "1"}
    refresh_token = create_refresh_token(data)
    decoded = decode_token(refresh_token)
    assert decoded["type"] == "refresh"


def test_invalid_token():
    """Test decoding an invalid token."""
    result = decode_token("invalid.token.here")
    assert result is None


def test_credential_encryption():
    """Test credential encryption and decryption."""
    plaintext = "my_admin_password"
    encrypted = encrypt_credential(plaintext)
    assert encrypted != plaintext
    decrypted = decrypt_credential(encrypted)
    assert decrypted == plaintext


def test_constant_time_compare():
    """Test constant time string comparison."""
    assert constant_time_compare("same", "same")
    assert not constant_time_compare("same", "different")
    # Different lengths should also work
    assert not constant_time_compare("short", "longer_string")
