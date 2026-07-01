"""Response models for dashboard monitoring API."""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class ConnectionPoolSummary(BaseModel):
    """Aggregated connection pool statistics."""
    used: Optional[int] = Field(default=None, description="Total used connections.")
    free: Optional[int] = Field(default=None, description="Total free connections.")
    ok: Optional[int] = Field(default=None, description="Total successful connections.")
    error: Optional[int] = Field(default=None, description="Total connection errors.")


class QpsSummary(BaseModel):
    """Queries-per-second metric."""
    questions: Optional[int] = Field(default=None, description="Total Questions counter value.")


class TrafficSummary(BaseModel):
    """Traffic statistics."""
    queries: Optional[int] = Field(default=None, description="Total executed queries.")


class MemoryMetric(BaseModel):
    """A single memory metric entry."""
    variable_name: str = Field(description="Memory metric name.")
    variable_value: str = Field(description="Memory metric value.")


class HostgroupEntry(BaseModel):
    """Connection pool entry for a single backend server."""
    hostgroup: int = Field(description="Hostgroup ID.")
    srv_host: str = Field(description="Backend server hostname/IP.")
    srv_port: int = Field(description="Backend server port.")
    status: str = Field(description="Server status (ONLINE/OFFLINE/SHUNNED).")
    ConnUsed: int = Field(default=0, description="Currently used connections.")
    ConnFree: int = Field(default=0, description="Currently free connections.")
    ConnOK: int = Field(default=0, description="Total successful connections.")
    ConnERR: int = Field(default=0, description="Total connection errors.")
    Queries: int = Field(default=0, description="Total queries sent.")
    Latency_us: int = Field(default=0, description="Current latency in microseconds.")


class QueryDigestEntry(BaseModel):
    """A single query digest entry."""
    hostgroup: int = Field(description="Hostgroup where the query was executed.")
    schemaname: Optional[str] = Field(default=None, description="Database schema name.")
    username: Optional[str] = Field(default=None, description="MySQL user.")
    digest_text: str = Field(description="Normalized query text.")
    count_star: int = Field(default=0, description="Execution count.")
    sum_time: float = Field(default=0, description="Total execution time (seconds).")
    min_time: float = Field(default=0, description="Minimum execution time (seconds).")
    max_time: float = Field(default=0, description="Maximum execution time (seconds).")
    avg_time: float = Field(default=0, description="Average execution time (seconds).")


class DashboardSnapshotResponse(BaseModel):
    """Full dashboard monitoring snapshot."""
    server_id: str = Field(description="ProxySQL server identifier.")
    connections: list[dict] = Field(
        default_factory=list,
        description="Connection pool summary (aggregated).",
    )
    qps: list[dict] = Field(
        default_factory=list,
        description="Queries-per-second data.",
    )
    traffic: list[dict] = Field(
        default_factory=list,
        description="Traffic statistics.",
    )
    memory: list[dict] = Field(
        default_factory=list,
        description="Memory metrics (top 20).",
    )
    hostgroups: list[dict] = Field(
        default_factory=list,
        description="Per-backend connection pool details.",
    )
    query_digest: list[dict] = Field(
        default_factory=list,
        description="Top query digests by execution time.",
    )
    timestamp: Optional[datetime] = Field(
        default=None,
        description="ISO 8601 snapshot timestamp.",
    )
