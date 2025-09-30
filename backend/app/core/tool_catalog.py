from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class ToolDefinition:
    tool_id: str
    name: str
    description: str


DEFAULT_TOOLS: List[ToolDefinition] = [
    ToolDefinition("flat_screwdriver", "Отвертка плоская", "Стандартная отвертка с плоским шлицем."),
    ToolDefinition("phillips_screwdriver", "Отвертка крестовая", "Классическая крестовая отвертка."),
    ToolDefinition(
        "offset_cross_screwdriver",
        "Отвертка на смещенный крест",
        "Отвертка с крестообразным наконечником под углом для труднодоступных мест.",
    ),
    ToolDefinition("brace", "Коловорот", "Ручной инструмент для сверления без электричества."),
    ToolDefinition(
        "safety_pliers",
        "Пассатижи контровочные",
        "Пассатижи с удлиненными губками для работы с проволокой и контровкой.",
    ),
    ToolDefinition("pliers", "Пассатижи универсальные", "Универсальные пассатижи для захвата и удержания деталей."),
    ToolDefinition("shears", "Шэрница", "Инструмент для прецизионной обработки тонких материалов."),
    ToolDefinition("adjustable_wrench", "Разводной ключ", "Разводной ключ для работы с крепежом разных размеров."),
    ToolDefinition("oil_can_opener", "Открывашка для банок с маслом", "Приспособление для вскрытия масляных канистр."),
    ToolDefinition(
        "double_ended_wrench",
        "Ключ рожковый/накидной 3/4",
        "Комбинированный ключ 3/4 дюйма с рожковой и накидной частью.",
    ),
    ToolDefinition("side_cutters", "Бокорезы", "Инструмент для бокового перекусывания проводов и кабелей."),
]


TOOL_LOOKUP: Dict[str, ToolDefinition] = {tool.tool_id: tool for tool in DEFAULT_TOOLS}


def get_default_tool_ids() -> List[str]:
    return [tool.tool_id for tool in DEFAULT_TOOLS]
