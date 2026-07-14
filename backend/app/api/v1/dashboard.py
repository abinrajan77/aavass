"""Tower admin dashboard stat cards — `00-architecture-and-standards.md` §3.2. Read access
mirrors the dashboard-aggregate latency budget in that doc's §4 (250ms/500ms) and the same
`VIEW_TOWER_DATA` gate every tower member (association member or flat owner) already holds."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission
from app.db.session import get_db
from app.schemas.dashboard import TowerDashboardStats
from app.services.dashboard import get_tower_dashboard_stats

router = APIRouter(prefix="/towers/{tower_id}/dashboard-stats", tags=["dashboard"])


@router.get("", response_model=TowerDashboardStats)
async def get_dashboard_stats(
    tower_id: UUID,
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("VIEW_TOWER_DATA")),
) -> TowerDashboardStats:
    return await get_tower_dashboard_stats(db, tower_id=tower_id)
