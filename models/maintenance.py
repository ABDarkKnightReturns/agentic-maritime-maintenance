from enum import Enum
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class MaintenanceType(str, Enum):
    CONDITION_BASED = "Condition-Based"     # AI-triggered
    PLANNED = "Planned"                     # PMS schedule
    CORRECTIVE = "Corrective"               # Post-failure repair
    EMERGENCY = "Emergency"                 # Immediate action required


class WorkOrderStatus(str, Enum):
    DRAFT = "Draft"                         # Agent created, pending human approval
    APPROVED = "Approved"                   # Chief Engineer approved
    SCHEDULED = "Scheduled"                 # Slotted into port schedule
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"


class SparePart(BaseModel):
    part_number: str
    description: str
    quantity: int
    lead_time_days: int
    onboard_stock: int
    reorder_required: bool = False


class WorkOrder(BaseModel):
    work_order_id: str                      # e.g. "WO-2026-0042"
    asset_id: str
    maintenance_type: MaintenanceType
    status: WorkOrderStatus = WorkOrderStatus.DRAFT
    priority: int = Field(ge=1, le=5)      # 1=Critical, 5=Low

    title: str
    description: str
    ai_rationale: str                       # Claude's reasoning for raising this WO

    # Scheduling
    created_at: datetime
    recommended_window: Optional[str] = None    # e.g. "Next port call — Hamburg 2026-05-22"
    estimated_duration_hours: float = 4.0
    requires_port: bool = False             # Can it be done at sea?
    requires_class_surveyor: bool = False

    # Human-in-the-loop gate
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    approval_notes: Optional[str] = None

    # Execution
    assigned_to: Optional[str] = None      # "2nd Engineer" / "Chief Engineer"
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    completion_notes: Optional[str] = None

    # Parts & cost
    spare_parts: list[SparePart] = Field(default_factory=list)
    estimated_cost_usd: Optional[float] = None
    actual_cost_usd: Optional[float] = None

    # Traceability
    triggered_by_event_id: Optional[str] = None
    pms_job_code: Optional[str] = None
    ism_reference: Optional[str] = None
