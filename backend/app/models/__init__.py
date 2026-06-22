"""Data models for the application."""
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime
from typing import Optional


class UserRole(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class UserBase(BaseModel):
    username: str
    email: Optional[str] = None
    role: UserRole = UserRole.VIEWER


class UserCreate(UserBase):
    password: str = Field(min_length=1, description="Password will be validated against the password policy")


class UserUpdate(BaseModel):
    email: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class UserLogin(BaseModel):
    username: str
    password: str


class User(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ServerConfigBase(BaseModel):
    name: str
    host: str = "127.0.0.1"
    port: int = 6032
    admin_user: str
    is_default: bool = False
    hide_tables: Optional[str] = None


class ServerConfigCreate(ServerConfigBase):
    admin_password: str


class ServerConfigUpdate(BaseModel):
    name: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    admin_user: Optional[str] = None
    admin_password: Optional[str] = None
    is_default: Optional[bool] = None
    hide_tables: Optional[str] = None


class ServerConfig(ServerConfigBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: User


class PasswordChange(BaseModel):
    old_password: str
    new_password: str = Field(min_length=1, description="New password will be validated against the password policy")


# ── Cluster Management Models ──

class ClusterMemberRole(str, Enum):
    MASTER = "master"
    SLAVE = "slave"


class ClusterGroupCreate(BaseModel):
    name: str
    description: Optional[str] = None
    master_server_id: Optional[str] = None
    sync_variables: Optional[str] = None


class ClusterGroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    master_server_id: Optional[str] = None
    sync_variables: Optional[str] = None


class ClusterGroup(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    master_server_id: Optional[str] = None
    sync_variables: Optional[str] = None
    member_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ClusterMember(BaseModel):
    cluster_id: str
    server_id: str
    role: str
    server_name: Optional[str] = None
    server_host: Optional[str] = None
    server_port: Optional[int] = None

    model_config = {"from_attributes": True}


class ClusterMemberAdd(BaseModel):
    server_id: str
    role: str = "slave"


class ClusterSyncRequest(BaseModel):
    modules: Optional[list[str]] = None
    auto_apply: bool = True
    auto_save: bool = False
    target_servers: Optional[list[str]] = None  # if None, sync to all slaves


class ClusterNodeStatus(BaseModel):
    server_id: str
    server_name: str
    host: str
    port: int
    role: str
    online: bool
    version: Optional[str] = None
    uptime_seconds: Optional[int] = None
    checksums_match: Optional[bool] = None
    error: Optional[str] = None


class ClusterStatusResponse(BaseModel):
    cluster_id: str
    cluster_name: str
    nodes: list[ClusterNodeStatus]
    config_consistency: Optional[dict] = None
