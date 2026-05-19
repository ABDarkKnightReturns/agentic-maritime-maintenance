"""
Work Order Store
-----------------
CRUD for WorkOrder objects. Agents create draft WOs; the UI presents them
for Chief Engineer approval (human-in-the-loop gate).
"""
import json
import threading
from datetime import datetime
from typing import Optional

from models.maintenance import WorkOrder, WorkOrderStatus
from storage.database import get_connection, initialise_schema
from loguru import logger


class WorkOrderStore:

    def __init__(self):
        initialise_schema()
        self._conn = get_connection()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def save_work_order(self, wo: WorkOrder):
        with self._lock:
            self._conn.execute(
                """INSERT OR REPLACE INTO work_orders
                   (work_order_id, asset_id, created_at, status, priority, title, payload)
                   VALUES (?,?,?,?,?,?,?)""",
                (
                    wo.work_order_id,
                    wo.asset_id,
                    wo.created_at.isoformat(),
                    wo.status.value,
                    wo.priority,
                    wo.title,
                    wo.model_dump_json(),
                ),
            )
            self._conn.commit()
        logger.info(f"[WOStore] Saved {wo.work_order_id} | {wo.status.value} | {wo.title}")

    def approve_work_order(self, work_order_id: str, approved_by: str, notes: str = ""):
        wo = self.get_work_order(work_order_id)
        if not wo:
            return
        wo.status = WorkOrderStatus.APPROVED
        wo.approved_by = approved_by
        wo.approved_at = datetime.utcnow()
        wo.approval_notes = notes
        self.save_work_order(wo)
        logger.info(f"[WOStore] Approved {work_order_id} by {approved_by}")

    def update_status(self, work_order_id: str, status: WorkOrderStatus):
        wo = self.get_work_order(work_order_id)
        if not wo:
            return
        wo.status = status
        self.save_work_order(wo)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_work_order(self, work_order_id: str) -> Optional[WorkOrder]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT payload FROM work_orders WHERE work_order_id=?",
                (work_order_id,),
            )
            row = cur.fetchone()
        return WorkOrder.model_validate_json(row["payload"]) if row else None

    def get_all_work_orders(
        self,
        asset_id: Optional[str] = None,
        status: Optional[WorkOrderStatus] = None,
        limit: int = 50,
    ) -> list[WorkOrder]:
        query = "SELECT payload FROM work_orders WHERE 1=1"
        params: list = []
        if asset_id:
            query += " AND asset_id=?"
            params.append(asset_id)
        if status:
            query += " AND status=?"
            params.append(status.value)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._lock:
            cur = self._conn.execute(query, params)
            rows = cur.fetchall()
        return [WorkOrder.model_validate_json(r["payload"]) for r in rows]

    def get_pending_approval(self) -> list[WorkOrder]:
        """Draft WOs waiting for Chief Engineer — shown in UI approval panel."""
        return self.get_all_work_orders(status=WorkOrderStatus.DRAFT)

    def get_summary(self) -> dict:
        with self._lock:
            cur = self._conn.execute(
                "SELECT status, COUNT(*) as cnt FROM work_orders GROUP BY status"
            )
            rows = cur.fetchall()
        return {r["status"]: r["cnt"] for r in rows}

    def clear_draft_orders(self):
        """Remove Draft work orders on fleet reset; preserves Approved/Completed history."""
        with self._lock:
            self._conn.execute(
                "DELETE FROM work_orders WHERE status=?",
                (WorkOrderStatus.DRAFT.value,),
            )
            self._conn.commit()
        logger.info("[WOStore] Draft work orders cleared on fleet reset")

    def get_context_for_agent(self, asset_id: str, n: int = 3) -> list[dict]:
        """Recent WOs for an asset — gives agents maintenance history context."""
        wos = self.get_all_work_orders(asset_id=asset_id, limit=n)
        return [
            {
                "work_order_id": wo.work_order_id,
                "title": wo.title,
                "status": wo.status.value,
                "created_at": wo.created_at.isoformat(),
                "maintenance_type": wo.maintenance_type.value,
                "ai_rationale": wo.ai_rationale,
            }
            for wo in wos
        ]
