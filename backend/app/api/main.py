from fastapi import APIRouter

from app.api.routes import items, login, private, users, utils, sessions, ingest_imu, ingest_gps, ingest_metrics, devices, auth
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)
api_router.include_router(items.router)
api_router.include_router(sessions.router)
api_router.include_router(ingest_imu.router)
api_router.include_router(ingest_gps.router)
api_router.include_router(ingest_metrics.router)
api_router.include_router(devices.router)
api_router.include_router(auth.router)


if settings.ENVIRONMENT == "local":
    api_router.include_router(private.router)
