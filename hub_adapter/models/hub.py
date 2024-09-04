"""Models for Hub endpoints."""

import datetime
import uuid
from enum import Enum

from pydantic import BaseModel


class ApprovalStatus(Enum):
    """Status of project possibilities."""
    approved: str = "approved"
    rejected: str = "rejected"


class BucketType(Enum):
    """Bucket types."""
    CODE: str = "CODE"
    RESULT: str = "RESULT"
    TEMP: str = "TEMP"


class AnalysisBuildStatus(Enum):
    """Possible values for analysis build status."""
    starting: str = "starting"
    started: str = "started"
    stopping: str = "stopping"
    stopped: str = "stopped"
    finished: str = "finished"
    failed: str = "failed"


class AnalysisNodeRunStatus(Enum):
    """Possible values for analysis run status."""
    running: str = "running"
    starting: str = "starting"
    started: str = "started"
    stopping: str = "stopping"
    stopped: str = "stopped"
    finished: str = "finished"
    failed: str = "failed"


class AnalysisRunStatus(Enum):
    """Possible values for analysis run status."""
    running: str = "running"
    starting: str = "starting"
    started: str = "started"
    stopping: str = "stopping"
    stopped: str = "stopped"
    finished: str = "finished"
    failed: str = "failed"


class AnalysisResultStatus(Enum):
    """Possible values for analysis build status."""
    started: str = "started"
    downloading: str = "downloading"
    downloaded: str = "downloaded"
    extracting: str = "extracting"
    extracted: str = "extracted"
    finished: str = "finished"
    failed: str = "failed"


class ConfigurationStatus(Enum):
    """"Possible values for configuration status."""
    base: str = "base"
    security_configured: str = "security_configured"
    resource_configured: str = "resource_configured"
    hash_generated: str = "hash_generated"
    hash_signed: str = "hash_signed"
    finished: str = "finished"


class BaseHubResponse(BaseModel):
    """Common attributes of Hub responses."""
    id: uuid.UUID
    created_at: datetime.datetime
    updated_at: datetime.datetime


class Registry(BaseHubResponse):
    """Details the registry information."""
    name: str | None = None
    host: str | None = None
    account_name: str | None = None
    account_secret: str | None = None


class MasterImage(BaseHubResponse):
    """Master image details."""
    path: str
    virtual_path: str
    group_virtual_path: str
    name: str
    command: str | None = None
    command_arguments: str | None = None


class Project(BaseHubResponse):
    """Single project response model."""
    name: str
    analyses: int
    realm_id: uuid.UUID
    user_id: uuid.UUID | None = None
    master_image_id: uuid.UUID | None = None
    master_image: MasterImage | None = None


class AllProjects(BaseModel):
    """List of all projects."""
    data: list[Project]
    meta: dict


class Node(BaseHubResponse):
    """Node details."""
    external_name: str | None = None
    name: str
    hidden: bool
    type: str
    online: bool
    registry_id: uuid.UUID | None = None
    registry_project_id: uuid.UUID | None = None
    robot_id: uuid.UUID
    realm_id: uuid.UUID


class ProjectNode(BaseHubResponse):
    """Single project proposal."""

    approval_status: ApprovalStatus
    comment: str | None = None
    project_id: uuid.UUID | None = None
    project_realm_id: uuid.UUID | None = None
    node_id: uuid.UUID | None = None
    node_realm_id: uuid.UUID | None = None
    project: Project | None = None
    node: Node | None = None


class ListProjectNodes(BaseModel):
    data: list[ProjectNode]
    meta: dict


class Analysis(BaseHubResponse):
    """Model representing a single detailed analysis."""
    name: str | None = None
    nodes: int
    configuration_status: ConfigurationStatus | None = None
    build_status: AnalysisBuildStatus | None = None
    run_status: AnalysisRunStatus | None = None
    registry_id: uuid.UUID | None = None
    realm_id: uuid.UUID
    user_id: uuid.UUID | None = None
    project_id: uuid.UUID
    project: Project | None = None
    master_image_id: uuid.UUID | None = None


class DetailedAnalysis(Analysis):
    """Model representing a single detailed analysis."""
    registry: Registry | None = None
    project: Project | None = None
    master_image: MasterImage | None = None


class AllAnalyses(BaseModel):
    """List of all projects."""
    data: list[DetailedAnalysis]
    meta: dict


class AnalysisNode(BaseHubResponse):
    """Node analysis response model."""
    approval_status: ApprovalStatus
    run_status: str | None = None
    comment: str | None = None
    index: int
    artifact_tag: str | None = None
    artifact_digest: str | None = None
    analysis_id: uuid.UUID
    analysis_realm_id: uuid.UUID
    node_id: uuid.UUID
    node_realm_id: uuid.UUID
    analysis: DetailedAnalysis | None = None
    node: Node | None = None


class PartialAnalysisNode(AnalysisNode):
    """Node analysis"""


class ListAnalysisNodes(BaseModel):
    data: list[AnalysisNode]
    meta: dict


class RegistryProject(BaseHubResponse):
    name: str | None = None
    type: str
    public: bool
    external_name: str | None = None
    external_id: str | None = None
    webhook_name: str | None = None
    webhook_exists: bool | None = None
    account_name: str | None = None
    account_secret: str | None = None
    registry_id: uuid.UUID | None = None
    registry: Registry | None = None
    realm_id: uuid.UUID | None = None


class AnalysisImageUrl(BaseModel):
    image_url: str
    project_id: str | None = None
    analysis_id: str
    registry_url: str
    registry_user: str | None = None
    registry_password: str | None = None


class Bucket(BaseHubResponse):
    """Bucket data."""
    type: BucketType
    external_id: str | None = None
    analysis_id: uuid.UUID | None = None
    analysis: DetailedAnalysis | None = None
    realm_id: uuid.UUID | None = None


class BucketList(BaseModel):
    data: list[Bucket]
    meta: dict


class PartialAnalysisBucketFile(BaseHubResponse):
    name: str | None = None
    root: bool
    external_id: str | None = None
    bucket_id: uuid.UUID | None = None
    bucket: Bucket | None = None
    analysis_id: uuid.UUID | None = None
    analysis: DetailedAnalysis | None = None
    realm_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    robot_id: uuid.UUID | None = None


class PartialBucketFilesList(BaseModel):
    data: list[PartialAnalysisBucketFile]
    meta: dict
