from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional


class SessionMode(str, Enum):
    HANDOUT = "handout"
    HANDOVER = "handover"


class SessionStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"


@dataclass
class SessionEngineer:
    id: int
    username: str


@dataclass
class DetectionItem:
    tool_id: Optional[str]
    label: str
    confidence: float


@dataclass
class AnalysisSnapshot:
    request_id: str
    image_filename: str
    detected: List[DetectionItem]
    matched_tool_ids: List[str]
    missing_tool_ids: List[str]
    unexpected_labels: List[str]
    match_ratio: float
    below_threshold: bool
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SessionRecord:
    session_id: str
    mode: SessionMode
    expected_tool_ids: List[str]
    threshold: float
    created_at: datetime = field(default_factory=datetime.utcnow)
    status: SessionStatus = SessionStatus.PENDING
    analyses: List[AnalysisSnapshot] = field(default_factory=list)
    engineer: Optional[SessionEngineer] = None

    def add_analysis(self, snapshot: AnalysisSnapshot) -> None:
        self.analyses.append(snapshot)

    def latest_analysis(self) -> Optional[AnalysisSnapshot]:
        if not self.analyses:
            return None
        return self.analyses[-1]
