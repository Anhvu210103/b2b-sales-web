"""Deal pipeline package."""

from app.deal_pipeline.stages import (
    DealStage,
    STAGE_CONFIG,
    VALID_TRANSITIONS,
    KANBAN_COLUMNS,
    get_stage_config,
    get_valid_transitions,
    is_valid_transition,
    get_stage_probability,
    get_next_actions,
    get_stage_order,
    get_kanban_columns,
    LOSS_REASONS,
    WIN_REASONS,
)
from app.deal_pipeline.kanban import (
    KanbanBoard,
    DealPipelineMetrics,
    PipelineForecaster,
    health_check,
)
from app.deal_pipeline.service import DealPipelineService

__all__ = [
    # Stages
    "DealStage",
    "STAGE_CONFIG",
    "VALID_TRANSITIONS",
    "KANBAN_COLUMNS",
    "get_stage_config",
    "get_valid_transitions",
    "is_valid_transition",
    "get_stage_probability",
    "get_next_actions",
    "get_stage_order",
    "get_kanban_columns",
    "LOSS_REASONS",
    "WIN_REASONS",
    # Kanban
    "KanbanBoard",
    "DealPipelineMetrics",
    "PipelineForecaster",
    "health_check",
    # Service
    "DealPipelineService",
]