from __future__ import annotations

import asyncio
import hashlib
import logging
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import httpx
import yaml

from ..core.config import AppConfig, get_config
from ..core.tool_catalog import TOOL_LOOKUP
from ..models.session import DetectionItem


@dataclass
class DetectionResult:
    tool_id: Optional[str]
    label: str
    confidence: float


logger = logging.getLogger(__name__)


@dataclass
class DetectionBackendInfo:
    backend: str
    configured: bool
    details: Dict[str, Optional[str]]
    classes: List[str]


class DetectionClient:
    """Interface for detection backends."""

    async def detect(self, image_path: Path) -> List[DetectionResult]:
        raise NotImplementedError

    async def describe(self) -> DetectionBackendInfo:
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

    async def describe(self) -> DetectionBackendInfo:
        return DetectionBackendInfo(
            backend="mock",
            configured=False,
            details={"latency_seconds": str(self._latency_seconds)},
            classes=[tool.name for tool in TOOL_LOOKUP.values()],
        )


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

    async def describe(self) -> DetectionBackendInfo:
        return DetectionBackendInfo(
            backend="http",
            configured=True,
            details={"base_url": self._base_url, "timeout": str(self._timeout)},
            classes=[],
        )


YOLO_INDEX_TO_TOOL_ID: Dict[int, str] = {
    0: "flat_screwdriver",
    1: "double_ended_wrench",
    2: "side_cutters",
    3: "phillips_screwdriver",
    4: "offset_cross_screwdriver",
    5: "brace",
    6: "safety_pliers",
    7: "pliers",
    8: "shears",
    9: "adjustable_wrench",
    10: "oil_can_opener",
}


class YoloDetectionClient(DetectionClient):
    """YOLOv11 detector using a local Ultralytics model."""

    def __init__(
        self,
        model_path: Path,
        dataset_config: Path,
        confidence_threshold: float,
        image_size: int,
        device: Optional[str] = None,
    ) -> None:
        self._model_path = model_path
        self._dataset_config = dataset_config
        self._confidence = confidence_threshold
        self._image_size = image_size
        self._device = device
        self._class_names = self._load_class_names(dataset_config)
        self._tool_lookup = TOOL_LOOKUP
        try:
            from ultralytics import YOLO  # type: ignore
        except ImportError as exc:  # pragma: no cover - runtime safeguard
            raise RuntimeError(
                "Ultralytics is required for YOLO detection. Install it via requirements.txt"
            ) from exc

        if not model_path.exists():
            raise FileNotFoundError(f"YOLO model weights not found: {model_path}")
        logger.info("Loading YOLO model from %s", model_path)
        self._model = YOLO(str(model_path))

    @staticmethod
    def _load_class_names(dataset_config: Path) -> Dict[int, str]:
        if not dataset_config.exists():
            raise FileNotFoundError(
                f"YOLO dataset configuration not found: {dataset_config}"
            )
        with dataset_config.open("r", encoding="utf-8") as stream:
            payload = yaml.safe_load(stream) or {}
        names = payload.get("names")
        if not isinstance(names, dict):
            raise ValueError("Invalid dataset.yaml: expected 'names' mapping")
        return {int(idx): str(name) for idx, name in names.items()}

    async def detect(self, image_path: Path) -> List[DetectionResult]:
        return await asyncio.to_thread(self._predict, image_path)

    def _predict(self, image_path: Path) -> List[DetectionResult]:
        results = self._model.predict(  # type: ignore[attr-defined]
            source=str(image_path),
            imgsz=self._image_size,
            conf=self._confidence,
            device=self._device,
            verbose=False,
        )
        detections: List[DetectionResult] = []
        for result in results:
            boxes = getattr(result, "boxes", None)
            if boxes is None:
                continue
            for box in boxes:
                cls_index = int(box.cls.item()) if hasattr(box.cls, "item") else int(box.cls)
                confidence = float(box.conf.item() if hasattr(box.conf, "item") else box.conf)
                label = self._class_names.get(cls_index, f"class_{cls_index}")
                tool_id = YOLO_INDEX_TO_TOOL_ID.get(cls_index)
                if tool_id and tool_id in self._tool_lookup:
                    label = self._tool_lookup[tool_id].name
                detections.append(
                    DetectionResult(tool_id=tool_id, label=label, confidence=round(confidence, 4))
                )
        return detections

    async def describe(self) -> DetectionBackendInfo:
        return DetectionBackendInfo(
            backend="yolo",
            configured=True,
            details={
                "model_path": str(self._model_path),
                "dataset_config": str(self._dataset_config),
                "confidence_threshold": str(self._confidence),
                "image_size": str(self._image_size),
                "device": self._device or "auto",
            },
            classes=[self._class_names[idx] for idx in sorted(self._class_names)],
        )


def detection_client_factory(config: AppConfig) -> DetectionClient:
    if config.detection_service_url:
        return HttpDetectionClient(config.detection_service_url, config.detection_timeout_seconds)

    try:
        return YoloDetectionClient(
            model_path=config.yolo_model_path,
            dataset_config=config.yolo_dataset_config,
            confidence_threshold=config.yolo_confidence_threshold,
            image_size=config.yolo_image_size,
            device=config.yolo_device,
        )
    except Exception as exc:  # pragma: no cover - fallback safety
        logger.warning("Falling back to mock detection client: %s", exc)
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
        _DETECTION_CLIENT = detection_client_factory(config)
    return _DETECTION_CLIENT
