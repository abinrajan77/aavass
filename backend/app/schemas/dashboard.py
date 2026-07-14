from decimal import Decimal

from pydantic import BaseModel


class TowerDashboardStats(BaseModel):
    """Aggregate stat-card data for the tower admin dashboard
    (`00-architecture-and-standards.md` §3.2 — "BentoGrid ... stat cards + quick links",
    "NumberTicker ... total collected this month, pending dues count, overdue amount").
    Read-only aggregation over Modules 2-4's own tables; never a cached/pre-computed snapshot.
    """

    total_flats: int
    occupied_flats: int
    vacant_flats: int
    total_collected_this_month: Decimal
    pending_dues_count: int
    overdue_dues_count: int
    overdue_amount: Decimal
    open_special_collections_count: int
    expenditure_this_month: Decimal
