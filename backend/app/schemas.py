from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator

from .core.tool_catalog import DEFAULT_TOOLS, TOOL_LOOKUP
from .models.session import SessionMode, SessionRecord, SessionStatus
from .services.dashboard_service import DashboardMetrics
from .services.detection_client import DetectionBackendInfo
from .db.models import EngineerORM


class ToolSchema(BaseModel):
    tool_id: str
    name: str
    description: str


class DetectionItemSchema(BaseModel):
    tool_id: Optional[str]
    label: str
    confidence: float

    class Config:
        orm_mode = True


class DetectionResponseSchema(BaseModel):
    detections: List[DetectionItemSchema]


class DetectionMetadataSchema(BaseModel):
    backend: str
    configured: bool
    details: Dict[str, Any] = Field(default_factory=dict)
    classes: List[str] = Field(default_factory=list)


class AnalysisSnapshotSchema(BaseModel):
    request_id: str
    image_filename: str
    detected: List[DetectionItemSchema]
    matched_tool_ids: List[str]
    missing_tool_ids: List[str]
    unexpected_labels: List[str]
    match_ratio: float
    below_threshold: bool
    created_at: datetime

    class Config:
        orm_mode = True


class SessionSchema(BaseModel):
    session_id: str
    mode: SessionMode
    expected_tool_ids: List[str]
    threshold: float
    created_at: datetime
    status: SessionStatus
    analyses: List[AnalysisSnapshotSchema] = Field(default_factory=list)
    engineer: Optional["SessionEngineerSchema"] = None

    class Config:
        orm_mode = True


class SessionEngineerSchema(BaseModel):
    id: int
    username: str

    class Config:
        orm_mode = True


class DashboardModeStat(BaseModel):
    mode: SessionMode
    count: int


class DashboardSessionSummarySchema(BaseModel):
    session_id: str
    created_at: datetime
    status: SessionStatus
    engineer_id: Optional[int] = None
    engineer_username: Optional[str] = None


class DashboardMetricsResponse(BaseModel):
    total_sessions: int
    pending_sessions: int
    completed_sessions: int
    total_engineers: int
    total_analyses: int
    sessions_by_mode: List[DashboardModeStat]
    latest_sessions: List[DashboardSessionSummarySchema]


class SessionCreateRequest(BaseModel):
    mode: SessionMode
    expected_tool_ids: Optional[List[str]] = None
    threshold: float = Field(default=0.9, ge=0.0, le=1.0)

    @validator("expected_tool_ids", each_item=True)
    def validate_tool_id(cls, value: str) -> str:
        if value not in TOOL_LOOKUP:
            raise ValueError(f"Unknown tool_id '{value}'")
        return value


class SessionCreateResponse(BaseModel):
    session_id: str
    mode: SessionMode
    expected_tool_ids: List[str]
    threshold: float
    engineer_id: Optional[int] = None


class AnalysisResponse(BaseModel):
    session_id: str
    session_status: SessionStatus
    analysis: AnalysisSnapshotSchema


class ToolCatalogResponse(BaseModel):
    tools: List[ToolSchema]


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


class EngineerProfileResponse(BaseModel):
    username: str
    role: str


class SessionListResponse(BaseModel):
    sessions: List[SessionSchema]


class EngineerSummary(BaseModel):
    username: str
    role: str
    created_at: datetime


class EngineerListResponse(BaseModel):
    engineers: List[EngineerSummary]


class EngineerCreateRequest(BaseModel):
    username: str = Field(..., min_length=3)
    password: str = Field(..., min_length=6)
    role: str = Field(default="engineer")

    @validator("role")
    def validate_role(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"admin", "engineer"}:
            raise ValueError("Role must be 'admin' or 'engineer'")
        return normalized


def serialize_tool_catalog() -> ToolCatalogResponse:
    return ToolCatalogResponse(
        tools=[
            ToolSchema(tool_id=tool.tool_id, name=tool.name, description=tool.description)
            for tool in DEFAULT_TOOLS
        ]
    )


def serialize_session(session: SessionRecord) -> SessionSchema:
    return SessionSchema.from_orm(session)


def serialize_sessions(sessions: List[SessionRecord]) -> SessionListResponse:
    return SessionListResponse(sessions=[serialize_session(session) for session in sessions])


def serialize_analysis(session: SessionRecord, analysis) -> AnalysisResponse:
    return AnalysisResponse(
        session_id=session.session_id,
        session_status=session.status,
        analysis=AnalysisSnapshotSchema.from_orm(analysis),
    )


def serialize_engineer(engineer: EngineerORM) -> EngineerSummary:
    return EngineerSummary(username=engineer.username, role=engineer.role, created_at=engineer.created_at)


def serialize_engineers(engineers: List[EngineerORM]) -> EngineerListResponse:
    return EngineerListResponse(engineers=[serialize_engineer(engineer) for engineer in engineers])


def serialize_dashboard_metrics(metrics: DashboardMetrics) -> DashboardMetricsResponse:
    return DashboardMetricsResponse(
        total_sessions=metrics.total_sessions,
        pending_sessions=metrics.pending_sessions,
        completed_sessions=metrics.completed_sessions,
        total_engineers=metrics.total_engineers,
        total_analyses=metrics.total_analyses,
        sessions_by_mode=[
            DashboardModeStat(mode=item.mode, count=item.count) for item in metrics.sessions_by_mode
        ],
        latest_sessions=[
            DashboardSessionSummarySchema(
                session_id=session.session_id,
                created_at=session.created_at,
                status=session.status,
                engineer_id=session.engineer_id,
                engineer_username=session.engineer_username,
            )
            for session in metrics.latest_sessions
        ],
    )


def serialize_detection_results(detections) -> DetectionResponseSchema:
    return DetectionResponseSchema(
        detections=[
            DetectionItemSchema(tool_id=item.tool_id, label=item.label, confidence=item.confidence)
            for item in detections
        ]
    )


def serialize_detection_metadata(info: DetectionBackendInfo) -> DetectionMetadataSchema:
    return DetectionMetadataSchema(
        backend=info.backend,
        configured=info.configured,
        details=info.details,
        classes=info.classes,
    )
