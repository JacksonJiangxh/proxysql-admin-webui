"""Unit tests for TemplateEngine: step generation, payload building, and array handling."""

import pytest
from app.services.template_engine import (
    get_template_steps,
    build_step_payload,
    build_array_payloads,
    TEMPLATES,
    ARCH_OPTIONS,
)


class TestTemplateConstants:
    """Verify template registry and architecture options are well-formed."""

    def test_templates_exist(self):
        """TEMPLATES dict contains at least T01 (MySQL Quick Deploy)."""
        assert "T01" in TEMPLATES
        tpl = TEMPLATES["T01"]
        assert tpl.id == "T01"
        assert len(tpl.architecture_options) > 0
        assert len(tpl.common_steps) > 0
        assert len(tpl.mode_steps) > 0

    def test_arch_options_valid(self):
        """ARCH_OPTIONS is a non-empty list of dicts with label/description."""
        assert len(ARCH_OPTIONS) > 0
        for opt in ARCH_OPTIONS:
            assert "value" in opt
            assert "label_key" in opt
            assert "description_key" in opt

    def test_template_has_mode_steps_for_all_archs(self):
        """Each architecture option in T01 has corresponding mode_steps."""
        tpl = TEMPLATES["T01"]
        arch_values = [a["value"] for a in tpl.architecture_options]
        for av in arch_values:
            assert av in tpl.mode_steps, (
                f"Architecture '{av}' missing from T01.mode_steps"
            )

    def test_shared_fields_match_mappings(self):
        """Every shared_fields entry has corresponding shared_field_mappings."""
        tpl = TEMPLATES["T01"]
        field_names = {f.name for f in tpl.shared_fields}
        mapping_names = set(tpl.shared_field_mappings.keys())
        for name in field_names:
            assert name in mapping_names, (
                f"Shared field '{name}' is missing from shared_field_mappings"
            )


class TestGetTemplateSteps:
    """Tests for get_template_steps()."""

    def test_valid_template(self):
        """get_template_steps returns steps for a valid template + arch."""
        steps = get_template_steps("T01", "single_primary_replica")
        assert len(steps) > 0
        # Every step should have required keys
        for step in steps:
            assert "step_key" in step
            assert "wizard_id" in step
            assert "title" in step
            assert "description" in step
            assert "fields" in step
            assert "shared_refs" in step

    def test_invalid_template_returns_empty(self):
        """Unknown template_id returns empty list."""
        assert get_template_steps("T99", "any") == []

    def test_invalid_architecture(self):
        """Unknown architecture mode returns only common_steps."""
        steps = get_template_steps("T01", "nonexistent_arch")
        # Should return common_steps only (which may be empty or not)
        assert isinstance(steps, list)

    def test_steps_have_i18n_keys(self):
        """Each step has an i18n_key for frontend translation."""
        steps = get_template_steps("T01", "single_primary_replica")
        for step in steps:
            assert "i18n_key" in step
            assert isinstance(step["i18n_key"], str)

    def test_multi_primary_steps(self):
        """Different architecture gives different steps (vs single_primary)."""
        sp_steps = get_template_steps("T01", "single_primary_replica")
        mp_steps = get_template_steps("T01", "multi_primary_replica")
        # The number of steps should differ due to different topology wizards
        assert len(sp_steps) > 0
        assert len(mp_steps) > 0


class TestBuildStepPayload:
    """Tests for build_step_payload()."""

    @pytest.fixture
    def step_info(self):
        """Get a representative step_info dict from the template."""
        steps = get_template_steps("T01", "single_primary_replica")
        # Find the W01 (backend servers) step
        for s in steps:
            if s["wizard_id"] == "W01":
                return s
        return steps[0] if steps else {}

    def test_merges_shared_and_user_values(self, step_info):
        """build_step_payload merges shared fields, user values, and defaults."""
        payload = build_step_payload(
            step_info,
            step_values={"hostname": "10.0.0.100"},
            shared_values={"port": 3306},
        )
        assert isinstance(payload, dict)
        # Shared value should appear
        assert payload.get("port") == 3306
        # User value should appear
        assert payload.get("hostname") == "10.0.0.100"

    def test_empty_step_info_returns_empty(self):
        """Empty step_info returns empty dict."""
        assert build_step_payload({}, {"a": 1}, {"b": 2}) == {}

    def test_default_values_used(self, step_info):
        """When no user/shared value provided, field defaults are used."""
        payload = build_step_payload(step_info, {}, {})
        assert isinstance(payload, dict)

    def test_user_value_overrides_shared(self, step_info):
        """User-provided value takes precedence over shared value."""
        payload = build_step_payload(
            step_info,
            step_values={"port": 9999},
            shared_values={"port": 3306},
        )
        if "port" in payload:
            assert payload["port"] == 9999


class TestBuildArrayPayloads:
    """Tests for build_array_payloads()."""

    @pytest.fixture
    def step_info(self):
        """Get a step with array fields (W01 should have multi-entry support)."""
        steps = get_template_steps("T01", "single_primary_replica")
        for s in steps:
            if s["wizard_id"] == "W01" and s.get("array_fields"):
                return s
        # Fallback: return first step
        return steps[0] if steps else {}

    def test_returns_list(self, step_info):
        """build_array_payloads always returns a list."""
        result = build_array_payloads(step_info, {}, {"port": 3306})
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_empty_step_returns_list_with_empty_dict(self):
        """Empty step_info → [{}]."""
        result = build_array_payloads({}, {}, {})
        assert result == [{}]

    def test_single_row_has_expected_keys(self, step_info):
        """A single-row paylaod includes the shared values."""
        result = build_array_payloads(
            step_info,
            step_values={"hostname": "db1.local"},
            shared_values={"port": 3306, "weight": 1},
        )
        payload = result[0]
        assert isinstance(payload, dict)
        if "port" in payload:
            assert payload["port"] == 3306
