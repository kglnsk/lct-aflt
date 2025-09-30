from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from ..schemas import (
    AnalysisResponse,
    EngineerProfileResponse,
    LoginRequest,
    SessionCreateRequest,
    SessionCreateResponse,
    SessionListResponse,
    SessionSchema,
    ToolCatalogResponse,
    TokenResponse,
    serialize_analysis,
    serialize_session,
    serialize_sessions,
    serialize_tool_catalog,
)
from ..services.session_service import SessionNotFoundError, SessionService
from ..services.detection_client import DetectionClient, get_detection_client
from ..services.auth_service import (
    AuthService,
    get_auth_service,
    get_bearer_credentials,
    get_current_engineer,
    require_admin,
)
from ..db.models import EngineerORM
from ..db.session import get_db

router = APIRouter()


def get_session_service(
    db: Session = Depends(get_db),
    detection_client: DetectionClient = Depends(get_detection_client),
) -> SessionService:
    return SessionService(db=db, detection_client=detection_client)


@router.get("/health", summary="Health check")
async def healthcheck() -> dict:
    return {"status": "ok"}


@router.get("/tools", response_model=ToolCatalogResponse, summary="List supported tools")
async def list_tools() -> ToolCatalogResponse:
    return serialize_tool_catalog()


@router.post("/auth/login", response_model=TokenResponse, summary="Authenticate engineer")
async def login(
    payload: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    engineer = auth_service.authenticate(payload.username, payload.password)
    if engineer is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = auth_service.issue_token(engineer)
    return TokenResponse(access_token=token, username=engineer.username, role=engineer.role)


@router.post(
    "/auth/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke the current access token",
)
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(get_bearer_credentials),
    auth_service: AuthService = Depends(get_auth_service),
) -> Response:
    auth_service.revoke_token(credentials.credentials)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/auth/me",
    response_model=EngineerProfileResponse,
    summary="Get current authenticated engineer profile",
)
async def read_current_engineer(
    engineer: EngineerORM = Depends(get_current_engineer),
) -> EngineerProfileResponse:
    return EngineerProfileResponse(username=engineer.username, role=engineer.role)


@router.post(
    "/sessions",
    response_model=SessionCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new hand-out or hand-over session",
)
async def create_session(
    request: SessionCreateRequest,
    service: SessionService = Depends(get_session_service),
) -> SessionCreateResponse:
    try:
        session = service.create_session(
            mode=request.mode,
            expected_tool_ids=request.expected_tool_ids,
            threshold=request.threshold,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return SessionCreateResponse(
        session_id=session.session_id,
        mode=session.mode,
        expected_tool_ids=session.expected_tool_ids,
        threshold=session.threshold,
    )


@router.get(
    "/admin/sessions",
    response_model=SessionListResponse,
    summary="List all sessions (admin only)",
)
async def admin_list_sessions(
    _: EngineerORM = Depends(require_admin),
    service: SessionService = Depends(get_session_service),
) -> SessionListResponse:
    sessions = service.list_sessions()
    return serialize_sessions(sessions)


@router.get(
    "/sessions/{session_id}",
    response_model=SessionSchema,
    summary="Get session details including past analyses",
)
async def get_session(
    session_id: str,
    service: SessionService = Depends(get_session_service),
) -> SessionSchema:
    try:
        session = service.get_session(session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return serialize_session(session)


@router.post(
    "/sessions/{session_id}/analyse",
    response_model=AnalysisResponse,
    summary="Analyse uploaded image for tool detection",
)
async def analyse_image(
    session_id: str,
    file: UploadFile = File(...),
    service: SessionService = Depends(get_session_service),
) -> AnalysisResponse:
    try:
        session = service.get_session(session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    allowed_media_types = {"image/jpeg", "image/png", "image/webp"}
    if not file.content_type or file.content_type not in allowed_media_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported media type '{file.content_type}'.",
        )

    analysis, updated_session = await service.analyse_image(
        session_id=session.session_id, upload=file
    )
    return serialize_analysis(updated_session, analysis)
