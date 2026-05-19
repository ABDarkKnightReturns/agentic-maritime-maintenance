"""Aggregates all KB chunks into a single list."""
from kb.data.failure_modes import FAILURE_MODES
from kb.data.maintenance_intervals import MAINTENANCE_INTERVALS
from kb.data.regulations import REGULATIONS
from kb.data.iacs_standards import IACS_STANDARDS
from kb.data.troubleshooting import TROUBLESHOOTING

ALL_CHUNKS: list[dict] = (
    FAILURE_MODES
    + MAINTENANCE_INTERVALS
    + REGULATIONS
    + IACS_STANDARDS
    + TROUBLESHOOTING
)
