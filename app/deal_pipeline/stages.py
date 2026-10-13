"""Deal pipeline stages and stage management."""

from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
from uuid import UUID
from datetime import datetime, timedelta


class DealStage(str, Enum):
    """Standard deal pipeline stages."""

    LEAD = "lead"                    # New lead, not yet qualified
    QUALIFIED = "qualified"          # Lead qualified, fits ICP
    DEMO_SCHEDULED = "demo_scheduled"  # Demo booked
    DEMO_COMPLETED = "demo_completed"  # Demo done
    PROPOSAL = "proposal"            # Proposal sent
    NEGOTIATION = "negotiation"      # Negotiating terms
    CONTRACT = "contract"            # Contract sent for signature
    WON = "won"                      # Deal closed won
    LOST = "lost"                    # Deal closed lost
    ON_HOLD = "on_hold"              # Temporarily on hold


# Stage metadata
STAGE_CONFIG = {
    DealStage.LEAD: {
        "label": "Lead mới",
        "order": 1,
        "color": "#6B7280",  # gray
        "probability": 10,
        "description": "Lead mới thu thập được, chưa định danh",
        "actions": ["qualify", "enrich", "assign"],
        "next_stages": [DealStage.QUALIFIED, DealStage.UNQUALIFIED],
    },
    DealStage.QUALIFIED: {
        "label": "Đã định danh",
        "order": 2,
        "color": "#3B82F6",  # blue
        "probability": 25,
        "description": "Lead phù hợp ICP, đã có nhu cầu rõ ràng",
        "actions": ["schedule_demo", "send_info", "discovery_call"],
        "next_stages": [DealStage.DEMO_SCHEDULED, DealStage.PROPOSAL, DealStage.LEAD],
    },
    DealStage.DEMO_SCHEDULED: {
        "label": "Đã đặt demo",
        "order": 3,
        "color": "#8B5CF6",  # purple
        "probability": 40,
        "description": "Demo đã được lên lịch",
        "actions": ["prepare_demo", "send_confirmation", "send_pre_read"],
        "next_stages": [DealStage.DEMO_COMPLETED, DealStage.QUALIFIED],
    },
    DealStage.DEMO_COMPLETED: {
        "label": "Demo xong",
        "order": 4,
        "color": "#8B5CF6",  # purple
        "probability": 50,
        "description": "Demo đã hoàn tất, chờ phản hồi",
        "actions": ["send_recap", "address_questions", "send_proposal"],
        "next_stages": [DealStage.PROPOSAL, DealStage.NEGOTIATION, DealStage.QUALIFIED],
    },
    DealStage.PROPOSAL: {
        "label": "Đã gửi đề xuất",
        "order": 5,
        "color": "#F59E0B",  # amber
        "probability": 65,
        "description": "Đề xuất giá đã được gửi",
        "actions": ["followup_proposal", "schedule_review_call", "send_case_study"],
        "next_stages": [DealStage.NEGOTIATION, DealStage.CONTRACT, DealStage.DEMO_COMPLETED],
    },
    DealStage.NEGOTIATION: {
        "label": "Đàm phán",
        "order": 6,
        "color": "#F97316",  # orange
        "probability": 80,
        "description": "Đang thương lượng điều khoản/giá",
        "actions": ["send_revised_proposal", "schedule_negotiation_call", "get_approval"],
        "next_stages": [DealStage.CONTRACT, DealStage.PROPOSAL, DealStage.LOST],
    },
    DealStage.CONTRACT: {
        "label": "Gửi hợp đồng",
        "order": 7,
        "color": "#10B981",  # emerald
        "probability": 90,
        "description": "Hợp đồng đã gửi chờ ký",
        "actions": ["followup_contract", "send_reminder", "escalate_if_needed"],
        "next_stages": [DealStage.WON, DealStage.NEGOTIATION],
    },
    DealStage.WON: {
        "label": "Thắng",
        "order": 8,
        "color": "#22C55E",  # green
        "probability": 100,
        "description": "Hợp đồng đã ký, deal thắng",
        "actions": ["onboard_customer", "handoff_to_cs", "request_referral"],
        "next_stages": [],
        "is_closed": True,
        "is_won": True,
    },
    DealStage.LOST: {
        "label": "Thua",
        "order": 9,
        "color": "#EF4444",  # red
        "probability": 0,
        "description": "Deal thất bại",
        "actions": ["log_loss_reason", "add_to_nurture", "schedule_reengage"],
        "next_stages": [DealStage.LEAD],
        "is_closed": True,
        "is_won": False,
    },
    DealStage.ON_HOLD: {
        "label": "Tạm hoãn",
        "order": 10,
        "color": "#6B7280",  # gray
        "probability": 25,
        "description": "Deal tạm hoãn, sẽ quay lại sau",
        "actions": ["set_reminder", "add_to_nurture", "schedule_reengage"],
        "next_stages": [DealStage.QUALIFIED, DealStage.LEAD],
    },
}


# Default stage probabilities for forecasting
DEFAULT_PROBABILITIES = {
    DealStage.LEAD: 10,
    DealStage.QUALIFIED: 25,
    DealStage.DEMO_SCHEDULED: 40,
    DealStage.DEMO_COMPLETED: 50,
    DealStage.PROPOSAL: 65,
    DealStage.NEGOTIATION: 80,
    DealStage.CONTRACT: 90,
    DealStage.WON: 100,
    DealStage.LOST: 0,
    DealStage.ON_HOLD: 25,
}


@dataclass
class StageTransition:
    """Represents a valid stage transition."""
    from_stage: DealStage
    to_stage: DealStage
    requires_reason: bool = False
    auto_actions: List[str] = None

    def __post_init__(self):
        if self.auto_actions is None:
            self.auto_actions = []


# Valid stage transitions
VALID_TRANSITIONS: List[StageTransition] = [
    # Forward progressions
    StageTransition(DealStage.LEAD, DealStage.QUALIFIED, auto_actions=["log_qualification"]),
    StageTransition(DealStage.LEAD, DealStage.LOST, requires_reason=True, auto_actions=["log_loss"]),
    StageTransition(DealStage.LEAD, DealStage.ON_HOLD, auto_actions=["schedule_reengage"]),

    StageTransition(DealStage.QUALIFIED, DealStage.DEMO_SCHEDULED, auto_actions=["schedule_demo"]),
    StageTransition(DealStage.QUALIFIED, DealStage.PROPOSAL, auto_actions=["send_proposal"]),
    StageTransition(DealStage.QUALIFIED, DealStage.LEAD, auto_actions=["log_disqualification"]),
    StageTransition(DealStage.QUALIFIED, DealStage.LOST, requires_reason=True, auto_actions=["log_loss"]),
    StageTransition(DealStage.QUALIFIED, DealStage.ON_HOLD, auto_actions=["schedule_reengage"]),

    StageTransition(DealStage.DEMO_SCHEDULED, DealStage.DEMO_COMPLETED, auto_actions=["log_demo_completion"]),
    StageTransition(DealStage.DEMO_SCHEDULED, DealStage.QUALIFIED, auto_actions=["reschedule_or_cancel"]),

    StageTransition(DealStage.DEMO_COMPLETED, DealStage.PROPOSAL, auto_actions=["send_proposal"]),
    StageTransition(DealStage.DEMO_COMPLETED, DealStage.NEGOTIATION, auto_actions=["start_negotiation"]),
    StageTransition(DealStage.DEMO_COMPLETED, DealStage.QUALIFIED, auto_actions=["log_feedback"]),

    StageTransition(DealStage.PROPOSAL, DealStage.NEGOTIATION, auto_actions=["start_negotiation"]),
    StageTransition(DealStage.PROPOSAL, DealStage.CONTRACT, auto_actions=["send_contract"]),
    StageTransition(DealStage.PROPOSAL, DealStage.DEMO_COMPLETED, auto_actions=["re_demo"]),

    StageTransition(DealStage.NEGOTIATION, DealStage.CONTRACT, auto_actions=["send_contract"]),
    StageTransition(DealStage.NEGOTIATION, DealStage.PROPOSAL, auto_actions=["revise_proposal"]),
    StageTransition(DealStage.NEGOTIATION, DealStage.LOST, requires_reason=True, auto_actions=["log_loss"]),

    StageTransition(DealStage.CONTRACT, DealStage.WON, auto_actions=["onboard_customer"]),
    StageTransition(DealStage.CONTRACT, DealStage.NEGOTIATION, auto_actions=["renegotiate"]),

    StageTransition(DealStage.ON_HOLD, DealStage.QUALIFIED, auto_actions=["re_engage"]),
    StageTransition(DealStage.ON_HOLD, DealStage.LEAD, auto_actions=["log_disqualification"]),

    # Allow moving back from WON/LOST to ON_HOLD for corrections
    StageTransition(DealStage.WON, DealStage.ON_HOLD, auto_actions=["log_correction"]),
    StageTransition(DealStage.LOST, DealStage.ON_HOLD, auto_actions=["log_correction"]),
]


# Kanban board column configuration
KANBAN_COLUMNS = [
    {"stage": DealStage.LEAD, "label": "Lead mới", "limit": 50, "color": "#6B7280"},
    {"stage": DealStage.QUALIFIED, "label": "Đã định danh", "limit": 30, "color": "#3B82F6"},
    {"stage": DealStage.DEMO_SCHEDULED, "label": "Đã đặt demo", "limit": 20, "color": "#8B5CF6"},
    {"stage": DealStage.DEMO_COMPLETED, "label": "Demo xong", "limit": 20, "color": "#8B5CF6"},
    {"stage": DealStage.PROPOSAL, "label": "Đã gửi đề xuất", "limit": 15, "color": "#F59E0B"},
    {"stage": DealStage.NEGOTIATION, "label": "Đàm phán", "limit": 10, "color": "#F97316"},
    {"stage": DealStage.CONTRACT, "label": "Gửi hợp đồng", "limit": 10, "color": "#10B981"},
    {"stage": DealStage.WON, "label": "Thắng ✓", "limit": None, "color": "#22C55E"},
    {"stage": DealStage.LOST, "label": "Thua ✗", "limit": None, "color": "#EF4444"},
    {"stage": DealStage.ON_HOLD, "label": "Tạm hoãn", "limit": 20, "color": "#6B7280"},
]


def get_stage_config(stage: DealStage) -> Dict:
    """Get configuration for a stage."""
    return STAGE_CONFIG.get(stage, {})


def get_valid_transitions(from_stage: DealStage) -> List[DealStage]:
    """Get valid next stages from current stage."""
    return [t.to_stage for t in VALID_TRANSITIONS if t.from_stage == from_stage]


def is_valid_transition(from_stage: DealStage, to_stage: DealStage) -> bool:
    """Check if transition is valid."""
    return any(t.from_stage == from_stage and t.to_stage == to_stage for t in VALID_TRANSITIONS)


def get_transition_info(from_stage: DealStage, to_stage: DealStage) -> Optional[StageTransition]:
    """Get transition info if valid."""
    for t in VALID_TRANSITIONS:
        if t.from_stage == from_stage and t.to_stage == to_stage:
            return t
    return None


def get_stage_probability(stage: DealStage) -> int:
    """Get default probability for a stage."""
    return DEFAULT_PROBABILITIES.get(stage, 0)


def is_closed_stage(stage: DealStage) -> bool:
    """Check if stage is a closed stage (won/lost)."""
    config = STAGE_CONFIG.get(stage, {})
    return config.get("is_closed", False)


def is_won_stage(stage: DealStage) -> bool:
    """Check if stage is a won stage."""
    config = STAGE_CONFIG.get(stage, {})
    return config.get("is_won", False)


def get_next_actions(stage: DealStage) -> List[str]:
    """Get recommended actions for a stage."""
    config = STAGE_CONFIG.get(stage, {})
    return config.get("actions", [])


def get_stage_order(stage: DealStage) -> int:
    """Get stage order for sorting."""
    config = STAGE_CONFIG.get(stage, {})
    return config.get("order", 999)


def get_kanban_columns() -> List[Dict]:
    """Get Kanban board column configuration."""
    return KANBAN_COLUMNS


# Common loss reasons for tracking
LOSS_REASONS = [
    "price_too_high",
    "budget_insufficient",
    "competitor_chosen",
    "no_need_identified",
    "timing_not_right",
    "decision_maker_unreachable",
    "internal_priority_change",
    "technical_mismatch",
    "contract_terms_unacceptable",
    "other",
]

# Common win reasons
WIN_REASONS = [
    "best_value_proposition",
    "better_features",
    "superior_support",
    "existing_relationship",
    "referral",
    "competitive_pricing",
    "demo_impressed",
    "trial_success",
    "reference_customer",
    "other",
]