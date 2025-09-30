from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session as OrmSession, selectinload

from ..db.models import AnalysisORM, EngineerORM, SessionORM
from ..models.session import SessionMode, SessionStatus


@dataclass
class ModeBreakdown:
    mode: SessionMode
    count: int


@dataclass
class DashboardSessionSummary:
    session_id: str
    created_at: datetime
    status: SessionStatus
    engineer_id: Optional[int]
    engineer_username: Optional[str]


@dataclass
class DashboardMetrics:
    total_sessions: int
    pending_sessions: int
    completed_sessions: int
    total_engineers: int
    total_analyses: int
    sessions_by_mode: List[ModeBreakdown]
    latest_sessions: List[DashboardSessionSummary]


class DashboardService:
    def __init__(self, db: OrmSession) -> None:
        self._db = db

    def collect_metrics(self, limit_latest: int = 5) -> DashboardMetrics:
        total_sessions = self._count_sessions()
        pending_sessions = self._count_sessions(status=SessionStatus.PENDING)
        completed_sessions = self._count_sessions(status=SessionStatus.COMPLETED)
        total_engineers = self._scalar(select(func.count()).select_from(EngineerORM))
        total_analyses = self._scalar(select(func.count()).select_from(AnalysisORM))
        sessions_by_mode = self._sessions_by_mode()
        latest_sessions = self._latest_sessions(limit_latest)

        return DashboardMetrics(
            total_sessions=total_sessions,
            pending_sessions=pending_sessions,
            completed_sessions=completed_sessions,
            total_engineers=total_engineers,
            total_analyses=total_analyses,
            sessions_by_mode=sessions_by_mode,
            latest_sessions=latest_sessions,
        )

    def _count_sessions(self, status: Optional[SessionStatus] = None) -> int:
        stmt = select(func.count()).select_from(SessionORM)
        if status is not None:
            stmt = stmt.where(SessionORM.status == status.value)
        return self._scalar(stmt)

    def _sessions_by_mode(self) -> List[ModeBreakdown]:
        stmt = select(SessionORM.mode, func.count()).group_by(SessionORM.mode)
        rows = self._db.execute(stmt).all()
        return [ModeBreakdown(mode=SessionMode(row[0]), count=row[1] or 0) for row in rows]

    def _latest_sessions(self, limit_latest: int) -> List[DashboardSessionSummary]:
        stmt = (
            select(SessionORM)
            .options(selectinload(SessionORM.engineer))
            .order_by(SessionORM.created_at.desc())
            .limit(limit_latest)
        )
        rows = self._db.scalars(stmt).all()
        summaries: List[DashboardSessionSummary] = []
        for session in rows:
            summaries.append(
                DashboardSessionSummary(
                    session_id=session.session_id,
                    created_at=session.created_at,
                    status=SessionStatus(session.status),
                    engineer_id=session.engineer.id if session.engineer else None,
                    engineer_username=session.engineer.username if session.engineer else None,
                )
            )
        return summaries

    def _scalar(self, stmt) -> int:
        value = self._db.scalar(stmt)
        if value is None:
            return 0
        return int(value)
