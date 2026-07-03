"""Wizard implementations organized by category.

This package contains the concrete wizard implementations for all 63
wizards (W01-W63) defined in the technical documentation. Wizards that
were already implemented in ``app.services.wizard_engine`` remain there;
this package provides the additional implementations that replace the
former "planned" stubs.

Modules:
    query_base   - QueryWizard base class for read-only monitoring wizards
    monitor      - W53-W63: Monitoring & diagnostics (read-only queries)
    ops          - W48, W49, W52: Backup / restore / cache flush
    system       - W32-W42: System configuration wizards
    firewall     - W43-W45: Firewall & security
    routing      - W18-W23: Query routing rules
    topology     - W25-W28: Replication & cluster topology
    server       - W03, W06-W08: Backend server management
    user         - W10, W14-W15: Backend user management
"""
from app.services.wizards.query_base import QueryWizard
from app.services.wizards.monitor import (
    SlowQueryAnalysisWizard, QueryCommandStatsWizard, QueryRuleHitsWizard,
    QueryErrorAnalysisWizard, ConnectionPoolMonitorWizard,
    RealtimeProcessListWizard, UserConnectionStatsWizard,
    BackendTopologyWizard, GlobalStatusWizard, GtidSyncStatusWizard,
    ClusterStatusWizard, MonitorCheckModeWizard,
)
from app.services.wizards.ops import (
    ConfigBackupWizard, ConfigRestoreWizard, FlushQueryCacheWizard,
)
from app.services.wizards.system import (
    MultiplexingVariablesWizard, LoggingEventsWizard, MonitorVariablesWizard,
    AdminUserManagementWizard, NetworkInterfaceWizard, ClusterNodeWizard,
    ClusterSyncVariablesWizard, SchedulerTaskWizard, RestApiRouteWizard,
    SslBackendWizard, CharsetVersionWizard,
)
from app.services.wizards.firewall import (
    FirewallUserWhitelistWizard, FirewallRuleWhitelistWizard,
    SqlInjectionProtectionWizard,
)
from app.services.wizards.routing import (
    QueryCacheRuleWizard, QueryRewriteRuleWizard, QueryTimeoutRuleWizard,
    QueryMirrorRuleWizard, FastRoutingWizard, QueryLoggingRuleWizard,
)
from app.services.wizards.topology import (
    GroupReplicationWizard, GaleraClusterWizard, AwsAuroraWizard,
    PgsqlReplicationWizard,
)
from app.services.wizards.server import (
    BatchImportServersWizard, ServerSslParamsWizard,
    HostgroupAttributesWizard, BackendConnectionTestWizard,
)
from app.services.wizards.user import (
    AddPgsqlUserWizard, LdapUserMappingWizard, FrontendBackendUserWizard,
)

__all__ = [
    "QueryWizard",
    # Monitoring
    "SlowQueryAnalysisWizard", "QueryCommandStatsWizard", "QueryRuleHitsWizard",
    "QueryErrorAnalysisWizard", "ConnectionPoolMonitorWizard",
    "RealtimeProcessListWizard", "UserConnectionStatsWizard",
    "BackendTopologyWizard", "GlobalStatusWizard", "GtidSyncStatusWizard",
    "ClusterStatusWizard", "MonitorCheckModeWizard",
    # Operations
    "ConfigBackupWizard", "ConfigRestoreWizard", "FlushQueryCacheWizard",
    # System
    "MultiplexingVariablesWizard", "LoggingEventsWizard", "MonitorVariablesWizard",
    "AdminUserManagementWizard", "NetworkInterfaceWizard", "ClusterNodeWizard",
    "ClusterSyncVariablesWizard", "SchedulerTaskWizard", "RestApiRouteWizard",
    "SslBackendWizard", "CharsetVersionWizard",
    # Firewall
    "FirewallUserWhitelistWizard", "FirewallRuleWhitelistWizard",
    "SqlInjectionProtectionWizard",
    # Routing
    "QueryCacheRuleWizard", "QueryRewriteRuleWizard", "QueryTimeoutRuleWizard",
    "QueryMirrorRuleWizard", "FastRoutingWizard", "QueryLoggingRuleWizard",
    # Topology
    "GroupReplicationWizard", "GaleraClusterWizard", "AwsAuroraWizard",
    "PgsqlReplicationWizard",
    # Server
    "BatchImportServersWizard", "ServerSslParamsWizard",
    "HostgroupAttributesWizard", "BackendConnectionTestWizard",
    # User
    "AddPgsqlUserWizard", "LdapUserMappingWizard", "FrontendBackendUserWizard",
]
