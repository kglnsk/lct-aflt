from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from ..schemas import (
    AnalysisResponse,
    DetectionMetadataSchema,
    DetectionResponseSchema,
    DashboardMetricsResponse,
    EngineerCreateRequest,
    EngineerListResponse,
    EngineerProfileResponse,
    LoginRequest,
    SessionCreateRequest,
    SessionCreateResponse,
    SessionListResponse,
    SessionSchema,
    ToolCatalogResponse,
    TokenResponse,
    serialize_analysis,
    serialize_detection_metadata,
    serialize_detection_results,
    serialize_engineer,
    serialize_engineers,
    serialize_session,
    serialize_sessions,
    serialize_dashboard_metrics,
    serialize_tool_catalog,
)
from ..services.session_service import SessionNotFoundError, SessionService
from ..services.dashboard_service import DashboardService
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
from ..core.config import AppConfig, get_config

router = APIRouter()


def get_session_service(
    db: Session = Depends(get_db),
    detection_client: DetectionClient = Depends(get_detection_client),
) -> SessionService:
    return SessionService(db=db, detection_client=detection_client)


def get_dashboard_service(
    db: Session = Depends(get_db),
) -> DashboardService:
    return DashboardService(db=db)


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
    engineer: EngineerORM = Depends(get_current_engineer),
    service: SessionService = Depends(get_session_service),
) -> SessionCreateResponse:
    try:
        session = service.create_session(
            mode=request.mode,
            engineer=engineer,
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
        engineer_id=session.engineer.id if session.engineer else None,
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
    "/admin/engineers",
    response_model=EngineerListResponse,
    summary="List all engineers (admin only)",
)
async def admin_list_engineers(
    _: EngineerORM = Depends(require_admin),
    auth_service: AuthService = Depends(get_auth_service),
) -> EngineerListResponse:
    engineers = auth_service.list_engineers()
    return serialize_engineers(engineers)


@router.post(
    "/admin/engineers",
    response_model=EngineerProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new engineer account (admin only)",
)
async def admin_create_engineer(
    payload: EngineerCreateRequest,
    _: EngineerORM = Depends(require_admin),
    auth_service: AuthService = Depends(get_auth_service),
) -> EngineerProfileResponse:
    try:
        engineer = auth_service.create_engineer(
            username=payload.username,
            password=payload.password,
            role=payload.role,
        )
    except ValueError as exc:
        message = str(exc)
        if "already exists" in message.lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message) from exc
    summary = serialize_engineer(engineer)
    return EngineerProfileResponse(username=summary.username, role=summary.role)


@router.get(
    "/sessions/{session_id}",
    response_model=SessionSchema,
    summary="Get session details including past analyses",
)
async def get_session(
    session_id: str,
    engineer: EngineerORM = Depends(get_current_engineer),
    service: SessionService = Depends(get_session_service),
) -> SessionSchema:
    try:
        session = service.get_session(session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if session.engineer and session.engineer.id != engineer.id and engineer.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough privileges")
    return serialize_session(session)


@router.post(
    "/sessions/{session_id}/analyse",
    response_model=AnalysisResponse,
    summary="Analyse uploaded image for tool detection",
)
async def analyse_image(
    session_id: str,
    file: UploadFile = File(...),
    engineer: EngineerORM = Depends(get_current_engineer),
    service: SessionService = Depends(get_session_service),
) -> AnalysisResponse:
    try:
        session = service.get_session(session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if session.engineer and session.engineer.id != engineer.id and engineer.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough privileges")

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


@router.get(
    "/admin/dashboard",
    response_model=DashboardMetricsResponse,
    summary="Aggregated metrics for the admin dashboard",
)
async def admin_dashboard(
    _: EngineerORM = Depends(require_admin),
    service: DashboardService = Depends(get_dashboard_service),
) -> DashboardMetricsResponse:
    metrics = service.collect_metrics()
    return serialize_dashboard_metrics(metrics)


async def _persist_upload_to_path(upload: UploadFile, target_dir: Path) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(upload.filename or "image.jpg").suffix or ".jpg"
    file_path = target_dir / f"det-{uuid.uuid4()}{suffix}"
    data = await upload.read()
    with file_path.open("wb") as file_obj:
        file_obj.write(data)
    await upload.seek(0)
    return file_path


@router.post(
    "/vision/detect",
    response_model=DetectionResponseSchema,
    summary="Run object detection on an uploaded image",
)
async def run_detection(
    file: UploadFile = File(...),
    engineer: EngineerORM = Depends(get_current_engineer),
    detection_client: DetectionClient = Depends(get_detection_client),
    config: AppConfig = Depends(get_config),
) -> DetectionResponseSchema:
    supported_types = {"image/jpeg", "image/png", "image/webp"}
    if file.content_type not in supported_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported media type '{file.content_type}'.",
        )

    temp_path = await _persist_upload_to_path(file, config.upload_dir / "ad-hoc")
    try:
        detections = await detection_client.detect(temp_path)
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except FileNotFoundError:
            pass
    return serialize_detection_results(detections)


@router.get(
    "/vision/status",
    response_model=DetectionMetadataSchema,
    summary="Inspect detection backend configuration",
)
async def detection_status(
    _: EngineerORM = Depends(get_current_engineer),
    detection_client: DetectionClient = Depends(get_detection_client),
) -> DetectionMetadataSchema:
    info = await detection_client.describe()
    return serialize_detection_metadata(info)
