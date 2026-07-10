from fastapi import APIRouter

from app.api.v1 import (
    association_members,
    audit_log,
    auth,
    complexes,
    expenditures,
    health,
    roles,
    special_collections,
    towers,
)

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health.router)
api_v1_router.include_router(auth.router)
api_v1_router.include_router(complexes.router)
api_v1_router.include_router(towers.router)
api_v1_router.include_router(roles.router)
api_v1_router.include_router(association_members.router)
api_v1_router.include_router(audit_log.router)
api_v1_router.include_router(special_collections.router)
api_v1_router.include_router(expenditures.router)
