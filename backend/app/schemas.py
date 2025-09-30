from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, validator

from .core.tool_catalog import DEFAULT_TOOLS, TOOL_LOOKUP
from .models.session import SessionMode, SessionRecord, SessionStatus


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

    class Config:
        orm_mode = True


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
