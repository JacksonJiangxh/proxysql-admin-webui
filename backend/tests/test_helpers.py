"""Tests for utility helper functions."""
import pytest
from app.utils.helpers import row_hash, split_commas, quote_ident, escape_like


class TestRowHash:
    """Tests for deterministic row hashing."""

    def test_same_rows_produce_same_hash(self):
        """Test that identical rows produce identical hashes."""
        row1 = {"id": 1, "name": "test", "value": 100}
        row2 = {"id": 1, "name": "test", "value": 100}
        assert row_hash(row1) == row_hash(row2)

    def test_different_rows_produce_different_hashes(self):
        """Test that different rows produce different hashes."""
        row1 = {"id": 1, "name": "test", "value": 100}
        row2 = {"id": 1, "name": "test", "value": 200}
        assert row_hash(row1) != row_hash(row2)

    def test_key_order_independence(self):
        """Test that key order does not affect hash."""
        row1 = {"a": 1, "b": 2, "c": 3}
        row2 = {"c": 3, "a": 1, "b": 2}
        assert row_hash(row1) == row_hash(row2)

    def test_empty_dict(self):
        """Test hash of empty dict."""
        assert isinstance(row_hash({}), str)

    def test_non_string_values(self):
        """Test hash with non-string/numeric values."""
        row = {"active": True, "name": "test"}
        result = row_hash(row)
        assert isinstance(result, str)
        assert len(result) > 0


class TestSplitCommas:
    """Tests for comma splitting with nested parentheses."""

    def test_simple_split(self):
        assert split_commas("a, b, c") == ["a", "b", "c"]

    def test_with_spaces(self):
        assert split_commas("  a  ,  b  ,  c  ") == ["a", "b", "c"]

    def test_with_nested_parentheses(self):
        parts = split_commas("a INT, b CHECK (x IN (1,2)), c VARCHAR")
        assert len(parts) == 3
        assert "b CHECK (x IN (1,2))" in parts[1]

    def test_single_value(self):
        assert split_commas("hello") == ["hello"]

    def test_empty_string(self):
        assert split_commas("") == []

    def test_deeply_nested(self):
        parts = split_commas("a, b(c(d(e))), f")
        assert len(parts) == 3

    def test_mixed_content(self):
        parts = split_commas("id INT NOT NULL, status VARCHAR CHECK (status IN ('A','B')) NOT NULL DEFAULT 'A'")
        assert len(parts) == 2
        assert "CHECK" in parts[1]


class TestQuoteIdent:
    """Tests for SQL identifier quoting."""

    def test_simple_identifier(self):
        assert quote_ident("mysql_servers") == "`mysql_servers`"

    def test_identifier_with_underscore_and_digits(self):
        assert quote_ident("mysql_query_rules_2") == "`mysql_query_rules_2`"

    def test_rejects_backtick_injection(self):
        """Backticks inside an identifier are now rejected (fail closed)."""
        with pytest.raises(ValueError):
            quote_ident("malicious`--")

    def test_rejects_double_quote_injection(self):
        with pytest.raises(ValueError):
            quote_ident('evil"; DROP TABLE x; --')

    def test_rejects_semicolon(self):
        with pytest.raises(ValueError):
            quote_ident("evil;")

    def test_rejects_empty_string(self):
        with pytest.raises(ValueError):
            quote_ident("")

    def test_rejects_none(self):
        with pytest.raises(ValueError):
            quote_ident(None)  # type: ignore[arg-type]

    def test_rejects_starting_with_digit(self):
        with pytest.raises(ValueError):
            quote_ident("1evil")

    def test_strips_surrounding_whitespace(self):
        """Leading/trailing whitespace is tolerated and stripped."""
        assert quote_ident("  mysql_servers  ") == "`mysql_servers`"


class TestEscapeLike:
    """Tests for LIKE pattern escaping."""

    def test_percent_escape(self):
        assert escape_like("100%") == "100!%"

    def test_underscore_escape(self):
        assert escape_like("test_name") == "test!_name"

    def test_bang_escape(self):
        """Test that ! is escaped first to prevent double-escaping."""
        assert escape_like("!") == "!!"

    def test_no_special_chars(self):
        assert escape_like("normal") == "normal"

    def test_mixed_special_chars(self):
        result = escape_like("50%_off!")
        assert result == "50!%!_off!!"
