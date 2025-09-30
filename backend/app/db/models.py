from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class SessionORM(Base):
    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    expected_tool_ids: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    analyses: Mapped[List["AnalysisORM"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="AnalysisORM.created_at",
        lazy="joined",
    )


class AnalysisORM(Base):
    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False
    )
    image_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    detected: Mapped[List[dict]] = mapped_column(JSON, nullable=False, default=list)
    matched_tool_ids: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    missing_tool_ids: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    unexpected_labels: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    match_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    below_threshold: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    session: Mapped[SessionORM] = relationship(back_populates="analyses")


class EngineerORM(Base):
    __tablename__ = "engineers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="engineer")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    tokens: Mapped[List["EngineerTokenORM"]] = relationship(
        back_populates="engineer", cascade="all, delete-orphan"
    )


class EngineerTokenORM(Base):
    __tablename__ = "engineer_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    engineer_id: Mapped[int] = mapped_column(Integer, ForeignKey("engineers.id", ondelete="CASCADE"))

    engineer: Mapped[EngineerORM] = relationship(back_populates="tokens")

