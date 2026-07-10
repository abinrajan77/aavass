from fastapi import APIRouter

from app.api.v1 import (
    association_members,
    audit_log,
    auth,
    complexes,
    flats,
    health,
    me_flats,
    owners,
    roles,
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
api_v1_router.include_router(flats.router)
api_v1_router.include_router(owners.router)
api_v1_router.include_router(me_flats.router)
