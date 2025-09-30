from __future__ import annotations

import asyncio
import hashlib
import random
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import httpx

from ..core.config import get_config
from ..core.tool_catalog import TOOL_LOOKUP
from ..models.session import DetectionItem


@dataclass
class DetectionResult:
    tool_id: Optional[str]
    label: str
    confidence: float


class DetectionClient:
    """Interface for detection backends."""

    async def detect(self, image_path: Path) -> List[DetectionResult]:
        raise NotImplementedError


class MockDetectionClient(DetectionClient):
    """Deterministic mock for vision inference used during MVP phase."""

    def __init__(self, latency_seconds: float = 0.05) -> None:
        self._latency_seconds = latency_seconds

    async def detect(self, image_path: Path) -> List[DetectionResult]:
        seed = self._seed_from_path(image_path)
        rng = random.Random(seed)
        tool_ids = list(TOOL_LOOKUP.keys())
        rng.shuffle(tool_ids)
        keep_count = rng.randint(max(1, len(tool_ids) // 2), len(tool_ids))
        selected = tool_ids[:keep_count]

        results: List[DetectionResult] = []
        for tool_id in selected:
            tool = TOOL_LOOKUP[tool_id]
            confidence = round(0.65 + rng.random() * 0.3, 3)
            results.append(
                DetectionResult(tool_id=tool_id, label=tool.name, confidence=confidence)
            )

        # Introduce occasional unknown detections to mimic false positives.
        if rng.random() > 0.6:
            results.append(
                DetectionResult(
                    tool_id=None,
                    label="Unknown object",
                    confidence=round(0.4 + rng.random() * 0.3, 3),
                )
            )
        if self._latency_seconds:
            await asyncio.sleep(self._latency_seconds)
        return results

    @staticmethod
    def _seed_from_path(image_path: Path) -> int:
        blob = f"{image_path.name}-{image_path.stat().st_size}".encode("utf-8")
        return int(hashlib.sha256(blob).hexdigest(), 16) % (2**32)


class HttpDetectionClient(DetectionClient):
    """HTTP client for integration with an external FastAPI detection service."""

    def __init__(self, base_url: str, timeout_seconds: float = 8.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    async def detect(self, image_path: Path) -> List[DetectionResult]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            files = {"file": (image_path.name, image_path.read_bytes(), "application/octet-stream")}
            response = await client.post(f"{self._base_url}/detect", files=files)
            response.raise_for_status()
            payload = response.json()

        detections: List[DetectionResult] = []
        for item in payload.get("detections", []):
            detections.append(
                DetectionResult(
                    tool_id=item.get("tool_id"),
                    label=item.get("label", ""),
                    confidence=float(item.get("confidence", 0.0)),
                )
            )
        return detections


def detection_client_factory(
    detection_service_url: Optional[str], timeout_seconds: float
) -> DetectionClient:
    if detection_service_url:
        return HttpDetectionClient(detection_service_url, timeout_seconds)
    return MockDetectionClient()


def detection_items_from_results(results: List[DetectionResult]) -> List[DetectionItem]:
    return [
        DetectionItem(tool_id=result.tool_id, label=result.label, confidence=result.confidence)
        for result in results
    ]


_DETECTION_CLIENT: Optional[DetectionClient] = None


def get_detection_client() -> DetectionClient:
    global _DETECTION_CLIENT
    if _DETECTION_CLIENT is None:
        config = get_config()
        _DETECTION_CLIENT = detection_client_factory(
            config.detection_service_url, config.detection_timeout_seconds
        )
    return _DETECTION_CLIENT
