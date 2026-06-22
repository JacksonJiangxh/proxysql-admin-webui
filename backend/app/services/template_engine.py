"""Template wizard engine — multi-step guided setup for ProxySQL.

A "template" combines several individual wizards (steps) into a single
guided flow so that beginners can configure a complete ProxySQL deployment
without needing to understand which individual wizards to run and in what
order.

Key concepts:
  - TemplateDefinition: defines the architecture mode, steps, shared fields,
    and field deduplication rules.
  - TemplateStep: one step in the flow — maps to an existing wizard, but
    with overridden defaults and possibly a subset of fields.
  - Shared fields (deduplication): fields that appear in multiple steps
    (e.g. hostgroup_id) are collected once on a "shared" page and
    auto-propagated to all steps that reference them.
"""

from dataclasses import dataclass, field
from typing import Any, Optional

from app.services.wizard_engine import WIZARD_REGISTRY, WizardField


# ── Data structures ──────────────────────────────────────────


@dataclass
class TemplateStepOverride:
    """Override a field's default/required/label within a template step.

    This lets the template customize the presentation of an existing
    wizard field — e.g. hiding advanced fields, providing better defaults,
    or changing the label to be more beginner-friendly.
    """
    field_name: str
    default: Any = None          # Override default (None = keep wizard original)
    label: str = ""              # Override label (empty = keep wizard original)
    required: Optional[bool] = None  # Override required (None = keep wizard original)
    hidden: bool = False         # Hide this field in the template step
    is_array: bool = False       # Allow dynamic add/remove (for multi-row entries)
    array_min: int = 1           # Minimum rows when is_array=True
    help_text: str = ""          # Override help text (empty = keep wizard original)


@dataclass
class TemplateStep:
    """One step in a template flow — maps to an existing wizard."""
    wizard_id: str               # References an existing wizard in WIZARD_REGISTRY
    title: str                   # Step title shown in the stepper UI
    description: str             # Step description
    guide: str = ""              # Beginner-friendly guide text
    skip_allowed: bool = False   # Whether the user can skip this step
    overrides: list = field(default_factory=list)  # List[TemplateStepOverride]
    # Additional fields that don't exist in the original wizard but are
    # needed for the template (e.g. array metadata)
    extra_fields: list = field(default_factory=list)  # List[WizardField]


@dataclass
class TemplateDefinition:
    """Complete template definition — multi-step guided setup."""
    id: str
    name: str
    description: str
    icon: str
    # Architecture modes this template supports
    architecture_options: list = field(default_factory=list)  # List[dict]
    # Steps shared across all architecture modes
    common_steps: list = field(default_factory=list)  # List[TemplateStep]
    # Mode-specific steps (key = architecture option value)
    mode_steps: dict = field(default_factory=dict)  # dict[str, list[TemplateStep]]
    # Fields that are shared across steps (deduplication)
    # When a shared field appears in multiple steps, it is only shown
    # once and auto-propagated.
    shared_fields: list = field(default_factory=list)  # List[WizardField]
    # Mapping: shared_field_name -> list of (step_index, wizard_field_name)
    # that should be auto-populated from the shared field
    shared_field_mappings: dict = field(default_factory=dict)


# ── Architecture option definitions ──────────────────────

ARCH_OPTIONS = [
    {
        "value": "single_primary_replica",
        "label": "Single Primary + Replica",
        "description": "Traditional single-writer with read replicas, suitable for most scenarios",
        "icon": "server",
        "topology_type": "replication",
    },
    {
        "value": "multi_primary_replica",
        "label": "Multi-Primary + Replica",
        "description": "Multiple write nodes with read replicas, suitable for high write concurrency",
        "icon": "servers",
        "topology_type": "replication",
    },
    {
        "value": "group_replication_single_primary",
        "label": "MGR Single-Primary",
        "description": "MySQL Group Replication single-primary mode, automatic failover",
        "icon": "shield",
        "topology_type": "group_replication",
    },
    {
        "value": "group_replication_multi_primary",
        "label": "MGR Multi-Primary",
        "description": "MySQL Group Replication multi-primary mode, all nodes writable",
        "icon": "shuffle",
        "topology_type": "group_replication",
    },
    {
        "value": "galera_cluster",
        "label": "Galera Cluster",
        "description": "Galera/PXC multi-primary synchronous replication cluster",
        "icon": "link",
        "topology_type": "galera",
    },
]


# ── Template definitions ────────────────────────────────────

TEMPLATES: dict[str, TemplateDefinition] = {
    "T01": TemplateDefinition(
        id="T01",
        name="MySQL Quick Deploy Template",
        description="One-click configuration of a complete ProxySQL + MySQL proxy architecture, including backend servers, users, read/write splitting rules, and system variables",
        icon="rocket",
        architecture_options=ARCH_OPTIONS,
        # Shared fields — only entered once, auto-propagated to steps
        shared_fields=[
            WizardField("writer_hostgroup", "Writer Hostgroup", "number",
                        required=True, default=0,
                        help_text="Hostgroup number for write requests"),
            WizardField("reader_hostgroup", "Reader Hostgroup", "number",
                        required=True, default=1,
                        help_text="Hostgroup number for read requests"),
            WizardField("monitor_username", "Monitor Username", "text",
                        required=True, default="monitor",
                        help_text="ProxySQL user for checking backend MySQL health"),
            WizardField("monitor_password", "Monitor Password", "password",
                        required=True, default="monitor",
                        help_text="Password for the monitor user"),
        ],
        # shared_field_mappings: shared_field_name -> [(wizard_id, wizard_field_name)]
        # Maps shared fields to wizard field names in each step that should
        # auto-inherit the shared value.
        shared_field_mappings={
            "writer_hostgroup": [
                ("W01", "hostgroup_id"),
                ("W24", "writer_hostgroup"),
                ("W25", "writer_hostgroup"),
                ("W26", "writer_hostgroup"),
                ("W16", "writer_hostgroup"),
                ("W09", "default_hostgroup"),
            ],
            "reader_hostgroup": [
                ("W24", "reader_hostgroup"),
                ("W25", "reader_hostgroup"),
                ("W26", "reader_hostgroup"),
                ("W16", "reader_hostgroup"),
                ("W27", "reader_hostgroup"),
            ],
            "monitor_username": [
                ("W34", "monitor_username_shared"),
            ],
            "monitor_password": [
                ("W34", "monitor_password_shared"),
            ],
        },
        # Steps common to all modes
        common_steps=[
            TemplateStep(
                wizard_id="W01",
                title="Add MySQL Backend Server",
                description="Configure the backend MySQL server addresses and parameters that ProxySQL connects to",
                guide="Enter your MySQL server address. If you have multiple servers (primary + replicas), click 'Add Row' to add more rows. Advanced parameters are pre-filled with recommended defaults.",
                skip_allowed=False,
                overrides=[
                    TemplateStepOverride("hostgroup_id", hidden=True),  # auto from shared
                    TemplateStepOverride("hostname", required=True),
                    TemplateStepOverride("port", default=3306),
                    TemplateStepOverride("status", default="ONLINE"),
                    TemplateStepOverride("weight", default=1),
                    TemplateStepOverride("max_connections", default=1000),
                    TemplateStepOverride("max_replication_lag", default=30),
                    TemplateStepOverride("use_ssl", default=0),
                    TemplateStepOverride("max_latency_ms", default=0),
                    TemplateStepOverride("comment", hidden=True),
                    # hostname is an array field — allow dynamic add/remove
                    TemplateStepOverride("hostname", is_array=True, array_min=1),
                    TemplateStepOverride("port", is_array=True, array_min=1),
                    TemplateStepOverride("weight", is_array=True, array_min=1),
                    TemplateStepOverride("max_connections", is_array=True, array_min=1),
                    TemplateStepOverride("max_replication_lag", is_array=True, array_min=1),
                ],
            ),
            TemplateStep(
                wizard_id="W09",
                title="Create ProxySQL User",
                description="Configure the user credentials for applications connecting to ProxySQL",
                guide="Set the username and password that your application uses to connect to ProxySQL. The default_hostgroup is auto-inherited from the hostgroup configuration.",
                skip_allowed=False,
                overrides=[
                    TemplateStepOverride("username", required=True),
                    TemplateStepOverride("password", required=True),
                    TemplateStepOverride("default_hostgroup", hidden=True),  # auto from shared
                    TemplateStepOverride("active", default=1),
                    TemplateStepOverride("max_connections", default=10000),
                    TemplateStepOverride("transaction_persistent", default=1),
                    TemplateStepOverride("fast_forward", default=0),
                    TemplateStepOverride("schema_locked", default=0),
                    TemplateStepOverride("default_schema", default=""),
                    TemplateStepOverride("comment", hidden=True),
                ],
            ),
            TemplateStep(
                wizard_id="W16",
                title="Read/Write Splitting",
                description="Configure query routing rules for automatic read/write splitting",
                guide="ProxySQL automatically routes write requests to the Writer hostgroup and read requests to the Reader hostgroup. Hostgroup numbers are auto-inherited.",
                skip_allowed=True,
                overrides=[
                    TemplateStepOverride("writer_hostgroup", hidden=True),  # auto from shared
                    TemplateStepOverride("reader_hostgroup", hidden=True),  # auto from shared
                    TemplateStepOverride("check_type", default="read_only"),
                    TemplateStepOverride("cluster_name", default="cluster1"),
                    TemplateStepOverride("base_rule_id", default=10),
                    TemplateStepOverride("rule_select_for_update", default=True),
                    TemplateStepOverride("rule_dml", default=True),
                    TemplateStepOverride("rule_select", default=True),
                    TemplateStepOverride("rule_transaction", default=True),
                    TemplateStepOverride("_lookup", hidden=True),
                ],
            ),
            TemplateStep(
                wizard_id="W34",
                title="Monitor Configuration",
                description="Configure ProxySQL monitoring credentials and parameters for backend MySQL",
                guide="ProxySQL needs a monitor user to check backend MySQL health status. The monitor username and password are auto-inherited from the shared configuration.",
                skip_allowed=True,
                overrides=[
                    TemplateStepOverride("variables", default=None),
                ],
                extra_fields=[
                    # We replace the JSON textarea with beginner-friendly individual fields
                    WizardField("monitor_username_shared", "Monitor Username", "text",
                                required=True, default="monitor",
                                help_text="Auto-inherited from shared config, editable"),
                    WizardField("monitor_password_shared", "Monitor Password", "password",
                                required=True, default="monitor",
                                help_text="Auto-inherited from shared config, editable"),
                    WizardField("monitor_connect_interval", "Connect Check Interval (ms)", "number",
                                default=60000, help_text="Default: check every 60s"),
                    WizardField("monitor_ping_interval", "Ping Check Interval (ms)", "number",
                                default=10000, help_text="Default: ping every 10s"),
                    WizardField("monitor_read_only_interval", "Read-Only Check Interval (ms)", "number",
                                default=1000, help_text="Default: check read_only every 1s"),
                    WizardField("monitor_ping_timeout", "Ping Timeout (ms)", "number",
                                default=500),
                    WizardField("monitor_connect_timeout", "Connect Timeout (ms)", "number",
                                default=600),
                ],
            ),
            TemplateStep(
                wizard_id="W29",
                title="Connection Pool Configuration",
                description="Configure ProxySQL connection pool parameters",
                guide="Adjust connection pool size and timeout parameters. Defaults are suitable for most scenarios — use as-is or modify as needed.",
                skip_allowed=True,
                overrides=[
                    TemplateStepOverride("variables", default=None),
                ],
                extra_fields=[
                    WizardField("mysql_max_connections", "Max Connections", "number",
                                default=2048, help_text="Max total connections from ProxySQL to backends"),
                    WizardField("mysql_connect_timeout_server", "Backend Connect Timeout (ms)", "number",
                                default=10000),
                    WizardField("mysql_connect_timeout_server_max", "Backend Max Connect Timeout (ms)", "number",
                                default=10000),
                    WizardField("mysql_free_connections_pct", "Free Connections %", "number",
                                default=10, help_text="Percentage of idle connections to keep"),
                ],
            ),
        ],
        # Mode-specific topology steps
        mode_steps={
            "single_primary_replica": [
                TemplateStep(
                    wizard_id="W24",
                    title="Primary-Replica Topology",
                    description="Configure hostgroup mapping for traditional single-writer async replication",
                    guide="Set the mapping between the writer hostgroup and reader replica hostgroup. ProxySQL automatically distinguishes primary and replica via the read_only variable.",
                    skip_allowed=False,
                    overrides=[
                        TemplateStepOverride("writer_hostgroup", hidden=True),  # auto from shared
                        TemplateStepOverride("reader_hostgroup", hidden=True),  # auto from shared
                        TemplateStepOverride("check_type", default="read_only"),
                        TemplateStepOverride("comment", default="primary-replica"),
                    ],
                ),
            ],
            "multi_primary_replica": [
                TemplateStep(
                    wizard_id="W24",
                    title="Multi-Primary Topology",
                    description="Configure hostgroup mapping for multi-writer nodes with read replicas",
                    guide="Set the mapping between multiple writer hostgroups and reader replica hostgroups.",
                    skip_allowed=False,
                    overrides=[
                        TemplateStepOverride("writer_hostgroup", hidden=True),
                        TemplateStepOverride("reader_hostgroup", hidden=True),
                        TemplateStepOverride("check_type", default="read_only"),
                        TemplateStepOverride("comment", default="multi-primary-replica"),
                    ],
                ),
            ],
            "group_replication_single_primary": [
                TemplateStep(
                    wizard_id="W25",
                    title="MGR Single-Primary Topology",
                    description="Configure MySQL Group Replication single-primary mode hostgroups",
                    guide="In MGR single-primary mode, only one node accepts writes while others are read replicas. ProxySQL automatically monitors and routes traffic.",
                    skip_allowed=False,
                    overrides=[
                        TemplateStepOverride("writer_hostgroup", hidden=True),
                        TemplateStepOverride("reader_hostgroup", hidden=True),
                        TemplateStepOverride("offline_hostgroup", default=2,
                                              label="Offline Hostgroup",
                                              help_text="Hostgroup for unavailable nodes"),
                        TemplateStepOverride("backup_writer_hostgroup", default=3,
                                              label="Backup Writer Hostgroup"),
                        TemplateStepOverride("max_writers", default=1),
                        TemplateStepOverride("writer_is_also_reader", default=2),
                        TemplateStepOverride("max_transactions_behind", default=100),
                        TemplateStepOverride("comment", default="mgr-single-primary"),
                    ],
                ),
            ],
            "group_replication_multi_primary": [
                TemplateStep(
                    wizard_id="W25",
                    title="MGR Multi-Primary Topology",
                    description="Configure MySQL Group Replication multi-primary mode hostgroups",
                    guide="In MGR multi-primary mode, all nodes can accept writes. ProxySQL automatically distributes write requests across nodes.",
                    skip_allowed=False,
                    overrides=[
                        TemplateStepOverride("writer_hostgroup", hidden=True),
                        TemplateStepOverride("reader_hostgroup", hidden=True),
                        TemplateStepOverride("offline_hostgroup", default=2),
                        TemplateStepOverride("backup_writer_hostgroup", default=3),
                        TemplateStepOverride("max_writers", default=3,
                                              help_text="Maximum number of write nodes allowed in multi-primary mode"),
                        TemplateStepOverride("writer_is_also_reader", default=1),
                        TemplateStepOverride("max_transactions_behind", default=100),
                        TemplateStepOverride("comment", default="mgr-multi-primary"),
                    ],
                ),
            ],
            "galera_cluster": [
                TemplateStep(
                    wizard_id="W26",
                    title="Galera Cluster Topology",
                    description="Configure Galera/PXC cluster hostgroups",
                    guide="Galera cluster uses synchronous replication — all nodes have consistent data. ProxySQL automatically identifies node roles.",
                    skip_allowed=False,
                    overrides=[
                        TemplateStepOverride("writer_hostgroup", hidden=True),
                        TemplateStepOverride("reader_hostgroup", hidden=True),
                        TemplateStepOverride("offline_hostgroup", default=2),
                        TemplateStepOverride("backup_writer_hostgroup", default=3),
                        TemplateStepOverride("max_writers", default=1),
                        TemplateStepOverride("writer_is_also_reader", default=2),
                        TemplateStepOverride("max_transactions_behind", default=100),
                        TemplateStepOverride("comment", default="galera-cluster"),
                    ],
                ),
            ],
        },
    ),
}


# ── Template execution engine ─────────────────────────────────


def get_template_steps(template_id: str, architecture_mode: str) -> list[dict]:
    """Build the ordered list of steps for a given template + architecture mode.

    Returns a list of step dicts suitable for the frontend stepper UI.
    Each step includes:
      - step_key: unique key for this step
      - wizard_id: the underlying wizard
      - title, description, guide
      - skip_allowed
      - fields: the effective field list (original wizard fields + overrides)
      - array_fields: list of field names that support dynamic add/remove
      - shared_field_refs: which shared fields auto-populate this step's fields
    """
    template = TEMPLATES.get(template_id)
    if not template:
        return []

    # Build step sequence: common steps + mode-specific steps
    all_steps = list(template.common_steps)
    mode_steps = template.mode_steps.get(architecture_mode, [])
    all_steps.extend(mode_steps)

    # Mode-specific topology step i18n suffixes
    MODE_STEP_SUFFIX = {
        "single_primary_replica": "_sp",
        "multi_primary_replica": "_mp",
        "group_replication_single_primary": "_sp",
        "group_replication_multi_primary": "_mp",
        "galera_cluster": "_gc",
    }

    result = []
    for i, step in enumerate(all_steps):
        wizard = WIZARD_REGISTRY.get(step.wizard_id)
        if not wizard:
            continue

        # Build i18n key for this step: wizard_id for common steps,
        # wizard_id + mode suffix for mode-specific steps
        is_mode_step = i >= len(template.common_steps)
        i18n_key = step.wizard_id
        if is_mode_step:
            suffix = MODE_STEP_SUFFIX.get(architecture_mode, "")
            i18n_key = step.wizard_id + suffix

        wizard_fields = wizard.definition.fields
        override_map = {o.field_name: o for o in step.overrides}

        # Build effective field list
        effective_fields = []
        array_field_names = []
        shared_refs = {}

        # First add shared field references (mapped to this step)
        for shared_name, mappings in template.shared_field_mappings.items():
            for (step_key, wizard_field_name) in mappings:
                # step_key is a short identifier; we match by wizard_id
                # For simplicity we match by step position or wizard_id
                if step_key == step.wizard_id or step_key == f"step_{i}":
                    shared_refs[wizard_field_name] = shared_name

        # Process wizard fields
        for wf in wizard_fields:
            override = override_map.get(wf.name)
            if override and override.hidden:
                continue
            if override and override.is_array:
                array_field_names.append(wf.name)

            field_dict = {
                "name": wf.name,
                "label": override.label if override and override.label else wf.label,
                "type": wf.type,
                "required": override.required if override and override.required is not None else wf.required,
                "default": override.default if override and override.default is not None else wf.default,
                "options": wf.options,
                "help": wf.help_text,
                "placeholder": wf.placeholder,
                "min": wf.min,
                "max": wf.max,
                "is_array": override.is_array if override else False,
                "array_min": override.array_min if override else 1,
                "shared_from": shared_refs.get(wf.name),
            }
            if wf.lookup:
                field_dict["lookup"] = {
                    "table": wf.lookup.get("table", ""),
                    "label_template": wf.lookup.get("label_template", ""),
                    "linked_fields": wf.lookup.get("linked_fields", {}),
                    "allow_manual": wf.lookup.get("allow_manual", True),
                }

            effective_fields.append(field_dict)

        # Add extra fields specific to this template step
        for ef in step.extra_fields:
            field_dict = {
                "name": ef.name,
                "label": ef.label,
                "type": ef.type,
                "required": ef.required,
                "default": ef.default,
                "options": ef.options,
                "help": ef.help_text,
                "placeholder": ef.placeholder,
                "min": ef.min,
                "max": ef.max,
                "is_array": False,
                "shared_from": None,
                "template_extra": True,  # flag: this field is template-specific
            }
            effective_fields.append(field_dict)

        result.append({
            "step_key": f"step_{i}",
            "wizard_id": step.wizard_id,
            "i18n_key": i18n_key,
            "title": step.title,
            "description": step.description,
            "guide": step.guide,
            "skip_allowed": step.skip_allowed,
            "fields": effective_fields,
            "array_fields": array_field_names,
            "shared_refs": shared_refs,
        })

    return result


def build_step_payload(step_info: dict, step_values: dict, shared_values: dict) -> dict:
    """Build the wizard fields payload for a single step execution.

    Merges:
      1. Shared field values (auto-propagated)
      2. User-entered step values
      3. Defaults for fields not provided

    For template steps with extra_fields, we transform the extra fields
    into the format the underlying wizard expects (e.g. building the
    variables JSON dict for W34/W29).
    """
    wizard_id = step_info["wizard_id"]
    wizard = WIZARD_REGISTRY.get(wizard_id)
    if not wizard:
        return {}

    payload = {}

    # Start with shared values mapped to this step's fields
    for field_info in step_info["fields"]:
        shared_from = field_info.get("shared_from")
        if shared_from and shared_from in shared_values:
            payload[field_info["name"]] = shared_values[shared_from]

    # Override with user-entered step values
    for key, value in step_values.items():
        if key.startswith("_array_"):
            # Array field: _array_hostname = ["10.0.0.1", "10.0.0.2"]
            # These are handled specially in batch execution
            continue
        payload[key] = value

    # Handle template extra fields for monitor/variables wizards
    if wizard_id in ("W34", "W29", "W30", "W31"):
        variables_dict = {}
        # For W34 (monitor vars)
        if wizard_id == "W34":
            if "monitor_username_shared" in step_values:
                variables_dict["mysql-monitor_username"] = step_values["monitor_username_shared"]
            elif "monitor_username" in shared_values:
                variables_dict["mysql-monitor_username"] = shared_values["monitor_username"]
            if "monitor_password_shared" in step_values:
                variables_dict["mysql-monitor_password"] = step_values["monitor_password_shared"]
            elif "monitor_password" in shared_values:
                variables_dict["mysql-monitor_password"] = shared_values["monitor_password"]
            if step_values.get("monitor_connect_interval"):
                variables_dict["mysql-monitor_connect_interval"] = str(step_values["monitor_connect_interval"])
            if step_values.get("monitor_ping_interval"):
                variables_dict["mysql-monitor_ping_interval"] = str(step_values["monitor_ping_interval"])
            if step_values.get("monitor_read_only_interval"):
                variables_dict["mysql-monitor_read_only_interval"] = str(step_values["monitor_read_only_interval"])
            if step_values.get("monitor_ping_timeout"):
                variables_dict["mysql-monitor_ping_timeout"] = str(step_values["monitor_ping_timeout"])
            if step_values.get("monitor_connect_timeout"):
                variables_dict["mysql-monitor_connect_timeout"] = str(step_values["monitor_connect_timeout"])
            payload["variables"] = variables_dict

        # For W29 (connection pool vars)
        elif wizard_id == "W29":
            if step_values.get("mysql_max_connections"):
                variables_dict["mysql-max_connections"] = str(step_values["mysql_max_connections"])
            if step_values.get("mysql_connect_timeout_server"):
                variables_dict["mysql-connect_timeout_server"] = str(step_values["mysql_connect_timeout_server"])
            if step_values.get("mysql_connect_timeout_server_max"):
                variables_dict["mysql-connect_timeout_server_max"] = str(step_values["mysql_connect_timeout_server_max"])
            if step_values.get("mysql_free_connections_pct"):
                variables_dict["mysql-free_connections_pct"] = str(step_values["mysql_free_connections_pct"])
            payload["variables"] = variables_dict

    # Fill defaults for missing fields
    for field_info in step_info["fields"]:
        name = field_info["name"]
        if name not in payload and field_info.get("default") is not None:
            payload[name] = field_info["default"]

    return payload


def build_array_payloads(step_info: dict, step_values: dict, shared_values: dict) -> list[dict]:
    """For steps with array fields (e.g. multiple servers), build separate payloads per row.

    Returns a list of payloads, one per array row. Each payload is suitable
    for executing the underlying wizard once.
    """
    array_field_names = step_info.get("array_fields", [])
    if not array_field_names:
        # No array fields — single payload
        return [build_step_payload(step_info, step_values, shared_values)]

    # Determine the number of rows from the first array field
    first_array = array_field_names[0]
    array_key = f"_array_{first_array}"
    rows = step_values.get(array_key, [])
    if not rows:
        # Fallback: try to infer from individual array field values
        rows = [step_values.get(first_array, "")]
        if not rows[0]:
            rows = []

    num_rows = len(rows)
    if num_rows == 0:
        return []

    payloads = []
    for row_idx in range(num_rows):
        row_values = {}
        for af_name in array_field_names:
            arr_key = f"_array_{af_name}"
            arr = step_values.get(arr_key, [])
            if row_idx < len(arr):
                row_values[af_name] = arr[row_idx]
            else:
                # Use default if available
                default_val = None
                for f in step_info["fields"]:
                    if f["name"] == af_name and f.get("default") is not None:
                        default_val = f["default"]
                        break
                row_values[af_name] = default_val or ""

        # Merge non-array step values
        for key, value in step_values.items():
            if not key.startswith("_array_") and key not in array_field_names:
                row_values[key] = value

        payload = build_step_payload(step_info, row_values, shared_values)
        payloads.append(payload)

    return payloads
