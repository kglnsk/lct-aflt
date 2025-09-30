from __future__ import annotations

import uuid
from dataclasses import asdict
from pathlib import Path
from typing import List, Optional, Tuple

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession, selectinload

from ..core.config import get_config
from ..core.tool_catalog import TOOL_LOOKUP, get_default_tool_ids
from ..db.models import AnalysisORM, SessionORM
from ..models.session import (
    AnalysisSnapshot,
    DetectionItem,
    SessionMode,
    SessionRecord,
    SessionStatus,
)
from .detection_client import DetectionClient, detection_items_from_results


class SessionNotFoundError(Exception):
    pass


class SessionService:
    def __init__(self, db: OrmSession, detection_client: DetectionClient) -> None:
        self._db = db
        self._detection_client = detection_client
        self._config = get_config()

    def create_session(
        self,
        mode: SessionMode,
        expected_tool_ids: Optional[List[str]] = None,
        threshold: float = 0.9,
    ) -> SessionRecord:
        tools = expected_tool_ids or get_default_tool_ids()
        validated_tools = list(dict.fromkeys(tool_id for tool_id in tools if tool_id in TOOL_LOOKUP))
        if not validated_tools:
            raise ValueError("At least one valid tool_id must be provided")

        session = SessionORM(
            session_id=str(uuid.uuid4()),
            mode=mode.value,
            expected_tool_ids=validated_tools,
            threshold=threshold,
            status=SessionStatus.PENDING.value,
        )
        self._db.add(session)
        self._db.commit()
        self._db.refresh(session)
        return self._to_record(session)

    def list_sessions(self) -> List[SessionRecord]:
        stmt = (
            select(SessionORM)
            .options(selectinload(SessionORM.analyses))
            .order_by(SessionORM.created_at.desc())
        )
        sessions = self._db.scalars(stmt).all()
        return [self._to_record(session) for session in sessions]

    def get_session(self, session_id: str) -> SessionRecord:
        stmt = (
            select(SessionORM)
            .options(selectinload(SessionORM.analyses))
            .where(SessionORM.session_id == session_id)
        )
        session = self._db.scalars(stmt).first()
        if session is None:
            raise SessionNotFoundError(session_id)
        return self._to_record(session)

    async def analyse_image(
        self,
        session_id: str,
        upload: UploadFile,
    ) -> Tuple[AnalysisSnapshot, SessionRecord]:
        session = self._db.get(SessionORM, session_id)
        if session is None:
            raise SessionNotFoundError(session_id)

        saved_path = await self._persist_upload(upload)
        detection_results = await self._detection_client.detect(saved_path)
        detection_items = detection_items_from_results(detection_results)

        expected = set(session.expected_tool_ids or [])
        detected_tool_ids = {item.tool_id for item in detection_items if item.tool_id}
        matched_tool_ids = sorted(expected & detected_tool_ids)
        missing_tool_ids = sorted(expected - detected_tool_ids)
        unexpected = {
            item.label
            for item in detection_items
            if (item.tool_id and item.tool_id not in expected) or item.tool_id is None
        }
        unexpected_labels = sorted(unexpected)

        match_ratio = round(len(matched_tool_ids) / len(expected), 3) if expected else 1.0
        below_threshold = match_ratio < session.threshold

        snapshot = AnalysisSnapshot(
            request_id=str(uuid.uuid4()),
            image_filename=saved_path.name,
            detected=detection_items,
            matched_tool_ids=matched_tool_ids,
            missing_tool_ids=missing_tool_ids,
            unexpected_labels=unexpected_labels,
            match_ratio=match_ratio,
            below_threshold=below_threshold,
        )

        analysis_row = AnalysisORM(
            request_id=snapshot.request_id,
            session_id=session.session_id,
            image_filename=snapshot.image_filename,
            detected=[asdict(item) for item in snapshot.detected],
            matched_tool_ids=snapshot.matched_tool_ids,
            missing_tool_ids=snapshot.missing_tool_ids,
            unexpected_labels=snapshot.unexpected_labels,
            match_ratio=snapshot.match_ratio,
            below_threshold=snapshot.below_threshold,
            created_at=snapshot.created_at,
        )
        self._db.add(analysis_row)

        if not snapshot.missing_tool_ids and not snapshot.unexpected_labels and not snapshot.below_threshold:
            session.status = SessionStatus.COMPLETED.value

        self._db.commit()
        self._db.refresh(analysis_row)

        updated_session = self.get_session(session.session_id)
        return snapshot, updated_session

    async def _persist_upload(self, upload: UploadFile) -> Path:
        target_dir = self._config.upload_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        suffix = Path(upload.filename or "upload").suffix or ".bin"
        target_path = target_dir / f"{uuid.uuid4()}{suffix}"
        data = await upload.read()
        with target_path.open("wb") as file_obj:
            file_obj.write(data)
        await upload.seek(0)
        return target_path

    def _to_record(self, session_row: SessionORM) -> SessionRecord:
        record = SessionRecord(
            session_id=session_row.session_id,
            mode=SessionMode(session_row.mode),
            expected_tool_ids=list(session_row.expected_tool_ids or []),
            threshold=session_row.threshold,
            created_at=session_row.created_at,
            status=SessionStatus(session_row.status),
        )
        analyses = sorted(session_row.analyses or [], key=lambda item: item.created_at)
        for analysis in analyses:
            record.add_analysis(self._to_snapshot(analysis))
        return record

    def _to_snapshot(self, analysis_row: AnalysisORM) -> AnalysisSnapshot:
        detected_payload = analysis_row.detected or []
        detected_items = [
            DetectionItem(
                tool_id=item.get("tool_id"),
                label=item.get("label", ""),
                confidence=float(item.get("confidence", 0.0)),
            )
            for item in detected_payload
        ]
        return AnalysisSnapshot(
            request_id=analysis_row.request_id,
            image_filename=analysis_row.image_filename,
            detected=detected_items,
            matched_tool_ids=list(analysis_row.matched_tool_ids or []),
            missing_tool_ids=list(analysis_row.missing_tool_ids or []),
            unexpected_labels=list(analysis_row.unexpected_labels or []),
            match_ratio=analysis_row.match_ratio,
            below_threshold=analysis_row.below_threshold,
            created_at=analysis_row.created_at,
        )
