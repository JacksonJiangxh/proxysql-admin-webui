"""ProxySQL Admin WebUI services package."""
from app.services.proxysql import proxysql_service, ProxySQLService
from app.services.sync_service import sync_service, SyncService, SyncAction
from app.services.query_engine import query_engine, QueryEngine, QueryTarget
from app.services.schema_service import schema_service, SchemaService
from app.services.dashboard_service import dashboard_service, DashboardService
from app.services.wizard_engine import (
    BaseWizard, WizardDefinition, WizardField, WIZARD_REGISTRY,
)

__all__ = [
    "proxysql_service", "ProxySQLService",
    "sync_service", "SyncService", "SyncAction",
    "query_engine", "QueryEngine", "QueryTarget",
    "schema_service", "SchemaService",
    "dashboard_service", "DashboardService",
    "BaseWizard", "WizardDefinition", "WizardField", "WIZARD_REGISTRY",
]
